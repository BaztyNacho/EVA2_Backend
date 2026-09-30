"""
==========================================================================
 COMANDO: exportar_datos
 Uso:
   python manage.py exportar_datos --solo-catalogo
       -> datos/catalogo.json : SOLO categorías y productos (con la ruta de
          su foto). Es el archivo que se sube a GitHub: no contiene
          usuarios, contraseñas, carros ni órdenes.
   python manage.py exportar_datos
       -> datos/tienda.json : respaldo COMPLETO (usuarios con contraseña
          encriptada, catálogo, carros y órdenes). Es solo para uso
          personal: está en el .gitignore y nunca se sube a GitHub.
 --------------------------------------------------------------------------
 No se exportan datos que no tiene sentido trasladar: sesiones activas,
 tokens JWT en blacklist, permisos y tipos de contenido (Django los
 regenera solo con migrate).
 Usa dumpdata internamente y escribe el archivo directamente en UTF-8
 (redirigir con ">" en PowerShell lo guardaría en UTF-16 y luego fallaría
 la importación).
==========================================================================
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from carrito.models import Carrito
from catalogo.models import Categoria, Producto
from ordenes.models import Orden

CARPETA_DATOS = Path(settings.BASE_DIR) / 'datos'
ARCHIVO_CATALOGO = CARPETA_DATOS / 'catalogo.json'
ARCHIVO_COMPLETO = CARPETA_DATOS / 'tienda.json'


class Command(BaseCommand):
    help = 'Exporta el catálogo (--solo-catalogo) o un respaldo completo de la tienda a la carpeta datos/.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-catalogo', action='store_true',
            help='Exporta solo categorías y productos (archivo para GitHub, sin datos personales).',
        )

    def handle(self, *args, **opciones):
        CARPETA_DATOS.mkdir(exist_ok=True)
        solo_catalogo = opciones['solo_catalogo']
        archivo = ARCHIVO_CATALOGO if solo_catalogo else ARCHIVO_COMPLETO
        apps = ['catalogo'] if solo_catalogo else ['usuarios', 'catalogo', 'carrito', 'ordenes']

        # --------------------------------------------------------------
        # natural_foreign: los permisos y grupos de los usuarios se
        # guardan por su nombre y no por su id, que puede ser distinto
        # en la otra base de datos.
        # --------------------------------------------------------------
        call_command('dumpdata', *apps, natural_foreign=True, indent=2, output=str(archivo))

        # Revisión de las fotos: cada ruta guardada debe existir en media/
        productos_con_foto = Producto.objects.exclude(imagen='').exclude(imagen__isnull=True)
        faltantes = [p.nombre for p in productos_con_foto if not p.imagen.storage.exists(p.imagen.name)]

        self.stdout.write(self.style.SUCCESS(f'Datos exportados a {archivo.relative_to(settings.BASE_DIR)}'))
        resumen = (f'  Categorías: {Categoria.objects.count()} | '
                   f'Productos: {Producto.objects.count()} ({productos_con_foto.count()} con foto)')
        if not solo_catalogo:
            resumen += (f' | Usuarios: {get_user_model().objects.count()} | '
                        f'Carros: {Carrito.objects.count()} | Órdenes: {Orden.objects.count()}')
        self.stdout.write(resumen)
        if faltantes:
            self.stdout.write(self.style.WARNING(
                f'  Atención: {len(faltantes)} producto(s) apuntan a una foto que no está en media/: '
                + ', '.join(faltantes)
            ))
        if solo_catalogo:
            self.stdout.write('  Sube este archivo y la carpeta media/ (fotos) a GitHub.')
        else:
            self.stdout.write('  Respaldo personal: está en el .gitignore y no se sube a GitHub.')