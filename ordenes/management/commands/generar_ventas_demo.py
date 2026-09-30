"""
==========================================================================
 COMANDO: generar_ventas_demo
 Uso:
   python manage.py generar_ventas_demo            -> crea las ventas demo
   python manage.py generar_ventas_demo --borrar   -> elimina las ventas demo
 Opciones: --ordenes 70  --dias 90
 --------------------------------------------------------------------------
 Genera un historial de ventas de DEMOSTRACIÓN para el dashboard, usando
 los productos reales del catálogo, sin alterar el inventario:
 1. Guarda una "foto" del stock de cada producto.
 2. Crea clientes de prueba con prefijo 'demo_' (demo_cliente_1, ...).
 3. Crea órdenes repartidas en los últimos N días, con precios congelados
    igual que el checkout, y las procesa con la lógica REAL de
    services.py (pagar_orden descuenta stock, cancelar_orden lo repone).
 4. Ajusta las fechas de cada orden al día simulado.
 5. Restaura el stock de cada producto al valor exacto de la "foto".
 Estados finales: ENTREGADO (mayoría), CANCELADO o PENDIENTE. Nunca
 PAGADO: si una orden demo quedara pagada y luego se cancelara desde el
 panel, se repondría un stock que ya fue restaurado (inventario inflado).
 Todo ocurre dentro de transaction.atomic(): si algo falla, no queda nada.
==========================================================================
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalogo.models import Producto
from ordenes import services
from ordenes.models import ItemOrden, Orden

Usuario = get_user_model()

PREFIJO = 'demo_'
CLAVE_DEMO = 'DemoTienda2026'
NOMBRES = [
    ('Camila', 'Rojas'), ('Matías', 'González'), ('Valentina', 'Muñoz'), ('Benjamín', 'Soto'),
    ('Fernanda', 'Díaz'), ('Tomás', 'Pérez'), ('Javiera', 'Contreras'), ('Diego', 'Morales'),
]


class Command(BaseCommand):
    help = 'Genera (o elimina con --borrar) un historial de ventas de demostración sin alterar el stock.'

    def add_arguments(self, parser):
        parser.add_argument('--borrar', action='store_true', help='Elimina las órdenes y clientes demo.')
        parser.add_argument('--ordenes', type=int, default=70, help='Cantidad de órdenes a generar (por defecto 70).')
        parser.add_argument('--dias', type=int, default=90, help='Días hacia atrás a cubrir (por defecto 90).')

    def handle(self, *args, **opciones):
        if opciones['borrar']:
            self.borrar()
        else:
            self.generar(opciones['ordenes'], opciones['dias'])

    # ----------------------------------------------------------------------
    # ELIMINAR: primero las órdenes (la FK usuario usa PROTECT) y después
    # los clientes demo (sus carros se borran en cascada). No toca stock.
    # ----------------------------------------------------------------------
    @transaction.atomic
    def borrar(self):
        clientes = Usuario.objects.filter(username__startswith=PREFIJO)
        ordenes = Orden.objects.filter(usuario__in=clientes)
        cantidad_ordenes = ordenes.count()
        cantidad_clientes = clientes.count()
        ordenes.delete()   # sus ItemOrden se borran en cascada
        clientes.delete()  # sus carros se borran en cascada
        self.stdout.write(self.style.SUCCESS(
            f'Eliminados {cantidad_clientes} clientes demo y {cantidad_ordenes} órdenes demo. El stock no se modificó.'
        ))

    # ----------------------------------------------------------------------
    # GENERAR
    # ----------------------------------------------------------------------
    @transaction.atomic
    def generar(self, cantidad_ordenes, dias):
        productos = list(Producto.objects.all())
        if not productos:
            raise CommandError('No hay productos en el catálogo. Crea productos antes de generar ventas.')
        if Orden.objects.filter(usuario__username__startswith=PREFIJO).exists():
            raise CommandError('Ya existen ventas demo. Elimínalas primero con: python manage.py generar_ventas_demo --borrar')

        azar = random.Random(2026)  # semilla fija: mismo resultado en cada ejecución
        stock_original = {producto.id: producto.stock for producto in productos}
        clientes = self.crear_clientes()
        ahora = timezone.now()
        resumen = {Orden.Estado.ENTREGADO: 0, Orden.Estado.CANCELADO: 0, Orden.Estado.PENDIENTE: 0}

        for _ in range(cantidad_ordenes):
            # Estado final: 78% entregadas, 12% canceladas, 10% pendientes
            sorteo = azar.random()
            estado = (Orden.Estado.ENTREGADO if sorteo < .78
                      else Orden.Estado.CANCELADO if sorteo < .90
                      else Orden.Estado.PENDIENTE)

            # Fecha: más ventas en los días recientes (tendencia al alza).
            # Las pendientes son siempre de los últimos 5 días.
            if estado == Orden.Estado.PENDIENTE:
                dias_atras = azar.uniform(0, min(5, dias))
            else:
                dias_atras = azar.triangular(0, dias, 0)
            fecha = ahora - timedelta(days=dias_atras, hours=azar.uniform(0, 10))
            if fecha > ahora:
                fecha = ahora - timedelta(minutes=5)

            orden = self.crear_orden(azar.choice(clientes), productos, azar)
            self.procesar(orden, estado, azar)
            self.fijar_fechas(orden, fecha, azar)
            resumen[estado] += 1

        # Restaurar el stock exacto que había antes de ejecutar el comando
        for producto_id, stock in stock_original.items():
            Producto.objects.filter(pk=producto_id).update(stock=stock)

        self.stdout.write(self.style.SUCCESS(
            f'Se generaron {cantidad_ordenes} órdenes demo en los últimos {dias} días: '
            f'{resumen[Orden.Estado.ENTREGADO]} entregadas, {resumen[Orden.Estado.CANCELADO]} canceladas, '
            f'{resumen[Orden.Estado.PENDIENTE]} pendientes. El stock quedó igual que antes.'
        ))
        self.stdout.write(f'Clientes demo: {", ".join(c.username for c in clientes)} (clave: {CLAVE_DEMO})')

    def crear_clientes(self):
        """Crea (o reutiliza) los clientes demo. La señal les crea su carro."""
        clientes = []
        for numero, (nombre, apellido) in enumerate(NOMBRES, start=1):
            cliente, creado = Usuario.objects.get_or_create(
                username=f'{PREFIJO}cliente_{numero}',
                defaults={
                    'email': f'{PREFIJO}cliente_{numero}@tienda-demo.cl',
                    'first_name': nombre,
                    'last_name': apellido,
                    'rol': Usuario.Rol.CLIENTE,
                },
            )
            if creado:
                cliente.set_password(CLAVE_DEMO)
                cliente.save()
            clientes.append(cliente)
        return clientes

    def crear_orden(self, cliente, productos, azar):
        """
        Crea la orden igual que el checkout: estado PENDIENTE, precios,
        nombre y SKU congelados en ItemOrden, y el total calculado.
        """
        elegidos = azar.sample(productos, k=min(len(productos), azar.choice([1, 1, 1, 2, 2, 3])))
        orden = Orden.objects.create(usuario=cliente)
        items = [
            ItemOrden(
                orden=orden,
                producto=producto,
                nombre_producto=producto.nombre,
                sku=producto.sku,
                precio_unitario=producto.precio,
                cantidad=azar.choice([1, 1, 1, 2]),
            )
            for producto in elegidos
        ]
        ItemOrden.objects.bulk_create(items)
        orden.total = sum(item.subtotal for item in items)
        orden.save(update_fields=['total'])
        return orden

    def procesar(self, orden, estado, azar):
        """
        Lleva la orden a su estado final con la lógica real de services.py.
        Antes de pagar, si un producto no tiene stock suficiente, se le
        suma lo necesario para que la simulación no se detenga (al final
        el stock se restaura de todas formas).
        """
        if estado == Orden.Estado.PENDIENTE:
            return
        pagar = estado == Orden.Estado.ENTREGADO or azar.random() < .5
        if pagar:
            for item in orden.items.all():
                producto = Producto.objects.get(pk=item.producto_id)
                if producto.stock < item.cantidad:
                    Producto.objects.filter(pk=producto.pk).update(stock=item.cantidad + 10)
            services.pagar_orden(orden.id)
        if estado == Orden.Estado.ENTREGADO:
            services.entregar_orden(orden.id)
        else:
            services.cancelar_orden(orden.id)

    def fijar_fechas(self, orden, fecha, azar):
        """
        Las fechas auto_now/auto_now_add no se pueden asignar al guardar,
        así que se actualizan con .update() (un UPDATE directo en SQL).
        """
        orden.refresh_from_db()
        fecha_pago = fecha + timedelta(minutes=azar.randint(5, 180)) if orden.fecha_pago else None
        if fecha_pago and fecha_pago > timezone.now():
            fecha_pago = timezone.now()
        Orden.objects.filter(pk=orden.pk).update(
            fecha_creacion=fecha,
            fecha_pago=fecha_pago,
            fecha_actualizacion=fecha_pago or fecha,
        )