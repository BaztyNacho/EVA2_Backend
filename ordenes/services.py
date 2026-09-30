"""
==========================================================================
 SERVICIOS DE LA APP: ordenes  (LÓGICA TRANSACCIONAL DE STOCK)
 Aquí se concentra TODA la lógica de negocio que modifica el stock.
 Las vistas solo llaman a estas funciones; así la regla existe en un
 único lugar y se aplica igual si el pago lo confirma el cliente
 (/pagar/) o el administrador (/estado/).

 Reglas de la pauta:
   1. El stock NO se descuenta al agregar al carro ni en el checkout.
   2. Se descuenta en el momento exacto en que la orden pasa a PAGADO.
   3. Si el stock no alcanza al pagar, la transacción se RECHAZA.
   4. Si una orden PAGADA se CANCELA, el stock se REPONE.

 Herramientas usadas:
   - transaction.atomic(): todas las consultas del bloque se ejecutan
     como UNA sola transacción en PostgreSQL. Si algo falla, se hace
     ROLLBACK y no queda ningún cambio a medias (todo o nada).
   - select_for_update(): bloquea las filas leídas (SELECT ... FOR
     UPDATE) hasta que termina la transacción. Si dos clientes pagan
     al mismo tiempo el último producto, el segundo espera a que el
     primero termine y luego ve el stock ya actualizado.
   - F('stock'): la resta/suma se hace dentro de PostgreSQL
     (UPDATE ... SET stock = stock - X), no en memoria de Python.
==========================================================================
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalogo.models import Producto

from .models import Orden


# --------------------------------------------------------------------------
# EXCEPCIONES DE NEGOCIO
# Las vistas las capturan para responder con el código HTTP adecuado.
# --------------------------------------------------------------------------
class TransicionInvalida(Exception):
    """El cambio de estado no está permitido (ej: ENTREGADO -> PAGADO)."""


class StockInsuficiente(Exception):
    """Uno o más productos no tienen stock suficiente para pagar."""

    def __init__(self, detalle):
        super().__init__('Stock insuficiente para completar el pago.')
        self.detalle = detalle


def _bloquear_orden(orden_id, nuevo_estado):
    """
    ----------------------------------------------------------------------
    Obtiene la orden BLOQUEADA (select_for_update) y valida que la
    transición al nuevo estado esté permitida por TRANSICIONES_VALIDAS.
    Debe llamarse dentro de un transaction.atomic().
    ----------------------------------------------------------------------
    """
    orden = Orden.objects.select_for_update().get(pk=orden_id)
    if not orden.puede_cambiar_a(nuevo_estado):
        raise TransicionInvalida(
            f'No se puede cambiar una orden {orden.estado} a {nuevo_estado}.'
        )
    return orden


def pagar_orden(orden_id):
    """
    ----------------------------------------------------------------------
    PENDIENTE -> PAGADO  (descuento atómico de stock)
    Paso 1: bloquear la orden y validar la transición.
    Paso 2: bloquear los productos involucrados. Se ordenan por id para
            que todas las transacciones bloqueen en el mismo orden y no
            se produzcan bloqueos cruzados (deadlocks).
    Paso 3: validar el stock de TODOS los ítems antes de modificar nada.
            Si falta en alguno, se lanza StockInsuficiente: el bloque
            atomic hace ROLLBACK y la orden sigue PENDIENTE sin cambios.
    Paso 4: descontar el stock de cada producto.
    Paso 5: marcar la orden como PAGADO y registrar stock_descontado.
    ----------------------------------------------------------------------
    """
    with transaction.atomic():
        orden = _bloquear_orden(orden_id, Orden.Estado.PAGADO)
        items = list(orden.items.all())

        ids_productos = [item.producto_id for item in items if item.producto_id]
        productos = {
            producto.id: producto
            for producto in Producto.objects.select_for_update()
            .filter(id__in=ids_productos)
            .order_by('id')
        }

        # Paso 3: validación completa (todo o nada)
        faltantes = []
        for item in items:
            producto = productos.get(item.producto_id)
            if producto is None:
                faltantes.append({
                    'producto': item.nombre_producto,
                    'motivo': 'El producto ya no existe en el catálogo.',
                })
            elif producto.stock < item.cantidad:
                faltantes.append({
                    'producto': item.nombre_producto,
                    'solicitado': item.cantidad,
                    'disponible': producto.stock,
                })
        if faltantes:
            raise StockInsuficiente(faltantes)

        # Paso 4: descuento de stock dentro de PostgreSQL
        for item in items:
            Producto.objects.filter(pk=item.producto_id).update(
                stock=F('stock') - item.cantidad
            )

        # Paso 5: actualizar la orden
        orden.estado = Orden.Estado.PAGADO
        orden.stock_descontado = True
        orden.fecha_pago = timezone.now()
        orden.save(update_fields=['estado', 'stock_descontado', 'fecha_pago', 'fecha_actualizacion'])
        return orden


def cancelar_orden(orden_id):
    """
    ----------------------------------------------------------------------
    PENDIENTE o PAGADO -> CANCELADO  (reposición de stock)
    - Si la orden había descontado stock (stock_descontado=True, es
      decir, estaba PAGADA), se devuelve cada cantidad al catálogo.
    - Si estaba PENDIENTE, nunca descontó stock, así que no se repone
      nada (evita "inventar" stock).
    - Si un producto fue eliminado del catálogo (producto_id = NULL),
      no hay dónde reponerlo y se omite.
    ----------------------------------------------------------------------
    """
    with transaction.atomic():
        orden = _bloquear_orden(orden_id, Orden.Estado.CANCELADO)

        if orden.stock_descontado:
            for item in orden.items.filter(producto__isnull=False).order_by('producto_id'):
                Producto.objects.filter(pk=item.producto_id).update(
                    stock=F('stock') + item.cantidad
                )
            orden.stock_descontado = False

        orden.estado = Orden.Estado.CANCELADO
        orden.save(update_fields=['estado', 'stock_descontado', 'fecha_actualizacion'])
        return orden


def entregar_orden(orden_id):
    """
    ----------------------------------------------------------------------
    PAGADO -> ENTREGADO
    No modifica stock (ya se descontó al pagar). Solo cambia el estado.
    ----------------------------------------------------------------------
    """
    with transaction.atomic():
        orden = _bloquear_orden(orden_id, Orden.Estado.ENTREGADO)
        orden.estado = Orden.Estado.ENTREGADO
        orden.save(update_fields=['estado', 'fecha_actualizacion'])
        return orden


def cambiar_estado(orden_id, nuevo_estado):
    """
    ----------------------------------------------------------------------
    Punto de entrada único para el endpoint del administrador.
    Deriva a la función correspondiente según el estado solicitado.
    ----------------------------------------------------------------------
    """
    acciones = {
        Orden.Estado.PAGADO: pagar_orden,
        Orden.Estado.ENTREGADO: entregar_orden,
        Orden.Estado.CANCELADO: cancelar_orden,
    }
    return acciones[nuevo_estado](orden_id)