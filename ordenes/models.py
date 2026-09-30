"""
==========================================================================
 MODELOS DE LA APP: ordenes
 Registro histórico de las compras (Órdenes de Compra) y sus ítems.
 Ciclo de vida: PENDIENTE -> PAGADO -> ENTREGADO  (o CANCELADO)
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