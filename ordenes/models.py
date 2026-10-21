"""
==========================================================================
 MODELOS DE LA APP: ordenes
 Registro histórico de las compras (Órdenes de Compra) y sus ítems.
 Ciclo de vida: PENDIENTE -> PAGADO -> ENTREGADO  (o CANCELADO)
 Incluye TransaccionWebpay: el registro de cada intento de pago con
 Transbank (Webpay Plus) asociado a una orden.
==========================================================================
"""
import uuid

from django.conf import settings
from django.db import models

from catalogo.models import Producto


class Orden(models.Model):
    """
    ----------------------------------------------------------------------
    ORDEN DE COMPRA
    Se genera en el checkout a partir del contenido del carro.
    - codigo: UUID único e irrepetible que identifica la orden hacia el
      cliente (comprobante), distinto del id interno autoincremental.
    - estado: campo con CHOICES (requisito de la pauta).
    - total: se CONGELA al momento del checkout.
    - stock_descontado: bandera que indica si esta orden ya descontó
      stock. Se usa para reponerlo solo cuando corresponde al cancelar.
    - usuario: FK con PROTECT -> no se puede borrar un usuario que tenga
      órdenes, para no perder el historial de ventas.
    ----------------------------------------------------------------------
    """

    # ------------------------------------------------------------------
    # CHOICES del estado de la orden
    # ------------------------------------------------------------------
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de pago'
        PAGADO = 'PAGADO', 'Pagado'
        ENTREGADO = 'ENTREGADO', 'Entregado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    # ------------------------------------------------------------------
    # MÁQUINA DE ESTADOS: transiciones permitidas desde cada estado.
    # ENTREGADO y CANCELADO son estados finales (no cambian más).
    # ------------------------------------------------------------------
    TRANSICIONES_VALIDAS = {
        Estado.PENDIENTE: [Estado.PAGADO, Estado.CANCELADO],
        Estado.PAGADO: [Estado.ENTREGADO, Estado.CANCELADO],
        Estado.ENTREGADO: [],
        Estado.CANCELADO: [],
    }

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ordenes',
    )
    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    total = models.PositiveIntegerField(default=0, help_text='Total congelado en CLP')
    stock_descontado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_pago = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'orden'
        verbose_name_plural = 'órdenes'
        ordering = ['-fecha_creacion']

    def puede_cambiar_a(self, nuevo_estado):
        """Indica si la transición al nuevo estado está permitida."""
        return nuevo_estado in self.TRANSICIONES_VALIDAS.get(self.estado, [])

    def __str__(self):
        return f'Orden {self.codigo} - {self.get_estado_display()}'


class ItemOrden(models.Model):
    """
    ----------------------------------------------------------------------
    ÍTEM DE LA ORDEN (detalle histórico)
    Copia los datos del producto en el instante del checkout:
    nombre, SKU y precio_unitario quedan CONGELADOS, por lo que si el
    precio del catálogo cambia después, la venta no se ve afectada.
    - producto: FK con SET_NULL -> si el producto se elimina del
      catálogo, la orden conserva su historial gracias a la copia.
    ----------------------------------------------------------------------
    """
    orden = models.ForeignKey(
        Orden,
        on_delete=models.CASCADE,
        related_name='items',
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        related_name='items_orden',
    )
    nombre_producto = models.CharField(max_length=150)
    sku = models.CharField(max_length=50)
    precio_unitario = models.PositiveIntegerField(help_text='Precio congelado en CLP')
    cantidad = models.PositiveIntegerField()

    class Meta:
        verbose_name = 'ítem de orden'
        verbose_name_plural = 'ítems de orden'

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f'{self.cantidad} x {self.nombre_producto}'


class TransaccionWebpay(models.Model):
    """
    ----------------------------------------------------------------------
    TRANSACCIÓN WEBPAY PLUS (Transbank)
    Guarda CADA intento de pago con tarjeta de una orden. Una orden puede
    tener varios intentos (ej: el primero rechazado y el segundo
    aprobado), por eso es una FK y no una relación 1 a 1.
    - token: identificador que entrega Transbank al crear la transacción.
      Con él se confirma (commit) el pago cuando el cliente vuelve.
    - orden_compra: "buy_order" enviado a Transbank (máx. 26 caracteres).
    - monto: total cobrado, copiado de la orden al iniciar el pago.
    - codigo_autorizacion / ultimos_digitos / tipo_pago / cuotas: datos
      que devuelve Transbank al confirmar (comprobante del pago).
    - codigo_respuesta: 0 = aprobado; cualquier otro valor = rechazado.
    - detalle: mensaje interno (motivo de rechazo, anulación, error).
    - orden: FK con PROTECT -> no se puede borrar una orden con pagos.
    ----------------------------------------------------------------------
    """

    # ------------------------------------------------------------------
    # CHOICES del estado de la transacción
    # ------------------------------------------------------------------
    class Estado(models.TextChoices):
        INICIADA = 'INICIADA', 'Iniciada (cliente en Webpay)'
        AUTORIZADA = 'AUTORIZADA', 'Autorizada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'
        ANULADA = 'ANULADA', 'Anulada (pago devuelto)'
        ABORTADA = 'ABORTADA', 'Abortada por el cliente'
        ERROR = 'ERROR', 'Error'

    orden = models.ForeignKey(
        Orden,
        on_delete=models.PROTECT,
        related_name='transacciones',
    )
    token = models.CharField(max_length=100, unique=True)
    orden_compra = models.CharField(max_length=26)
    monto = models.PositiveIntegerField(help_text='Monto en CLP enviado a Transbank')
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.INICIADA,
    )
    codigo_respuesta = models.IntegerField(null=True, blank=True)
    codigo_autorizacion = models.CharField(max_length=20, blank=True)
    ultimos_digitos = models.CharField(max_length=4, blank=True)
    tipo_pago = models.CharField(max_length=4, blank=True, help_text='VD: débito, VN: crédito, etc.')
    cuotas = models.PositiveSmallIntegerField(null=True, blank=True)
    detalle = models.CharField(max_length=255, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'transacción Webpay'
        verbose_name_plural = 'transacciones Webpay'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.orden_compra} - {self.get_estado_display()}'