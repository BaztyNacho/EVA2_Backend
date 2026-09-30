"""
==========================================================================
 COMANDO: importar_datos
 Uso:  python manage.py importar_datos
 --------------------------------------------------------------------------
 Carga en una base de datos NUEVA los datos exportados con exportar_datos.
 Pasos previos en el otro computador: crear la base en PostgreSQL,
 configurar el .env y ejecutar python manage.py migrate.
 Archivo que se usa:
 - datos/catalogo.json (el que viene en GitHub): categorías y productos.
   Solo exige que no existan productos ni categorías, así que se puede
   crear el superusuario antes o después de importar.
 - Si no existe, datos/tienda.json (respaldo completo personal): exige
   que la base no tenga usuarios ni productos.
 Así nunca se mezclan ni se duplican datos.
 - Usa loaddata, que inserta cada registro con su id original, en una
   sola transacción, y luego ajusta los contadores de id de PostgreSQL
   para que los registros nuevos no choquen con los importados.
 - Durante la carga las señales reciben raw=True; por eso la señal del
   carro no crea carros duplicados (ver carrito/signals.py).
==========================================================================
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from carrito.models import Carrito
from catalogo.models import Categoria, Producto
from ordenes.models import Orden

CARPETA_DATOS = Path(settings.BASE_DIR) / 'datos'
ARCHIVO_CATALOGO = CARPETA_DATOS / 'catalogo.json'
ARCHIVO_COMPLETO = CARPETA_DATOS / 'tienda.json'


class Command(BaseCommand):
    help = 'Importa datos/catalogo.json (o datos/tienda.json) en una base de datos nueva.'

    def handle(self, *args, **opciones):
        Usuario = get_user_model()
        solo_catalogo = ARCHIVO_CATALOGO.exists()
        archivo = ARCHIVO_CATALOGO if solo_catalogo else ARCHIVO_COMPLETO

        if not archivo.exists():
            raise CommandError('No se encontró datos/catalogo.json ni datos/tienda.json. '
                               'Genera uno con: python manage.py exportar_datos --solo-catalogo')
        if Producto.objects.exists() or Categoria.objects.exists():
            raise CommandError('La base de datos ya tiene productos o categorías. importar_datos solo se usa '
                               'en una base nueva (recién migrada), para no mezclar ni duplicar datos.')
        if not solo_catalogo and Usuario.objects.exists():
            raise CommandError('Para importar el respaldo completo (tienda.json) la base no debe tener usuarios.')

        call_command('loaddata', str(archivo), verbosity=0)

        productos_con_foto = Producto.objects.exclude(imagen='').exclude(imagen__isnull=True)
        faltantes = [p.nombre for p in productos_con_foto if not p.imagen.storage.exists(p.imagen.name)]

        self.stdout.write(self.style.SUCCESS(f'Datos importados desde {archivo.relative_to(settings.BASE_DIR)}'))
        resumen = (f'  Categorías: {Categoria.objects.count()} | '
                   f'Productos: {Producto.objects.count()} ({productos_con_foto.count()} con foto)')
        if not solo_catalogo:
            resumen += (f' | Usuarios: {Usuario.objects.count()} | '
                        f'Carros: {Carrito.objects.count()} | Órdenes: {Orden.objects.count()}')
        self.stdout.write(resumen)
        if faltantes:
            self.stdout.write(self.style.WARNING(
                f'  Atención: faltan {len(faltantes)} foto(s) en la carpeta media/: ' + ', '.join(faltantes)
            ))
        if solo_catalogo:
            self.stdout.write('  Siguiente paso: python manage.py createsuperuser (queda como ADMINISTRADOR).')