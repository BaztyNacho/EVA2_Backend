"""
==========================================================================
 MODELOS DE LA APP: carrito
 Carro de compras PERSISTENTE en PostgreSQL.
 Como vive en la base de datos (y no en la sesión ni en el frontend),
 los ítems se conservan aunque el usuario cierre sesión o entre desde
 otro dispositivo.
==========================================================================
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalogo.models import Producto


class Carrito(models.Model):
    """
    ----------------------------------------------------------------------
    CARRO DE COMPRAS
    Relación 1 a 1 (OneToOneField) con el usuario: cada usuario tiene
    exactamente UN carro activo, identificado por su usuario_id.
    Al hacer checkout el carro no se borra: solo se vacían sus ítems,
    así queda listo para la siguiente compra.
    ----------------------------------------------------------------------
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='carrito',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'carrito'
        verbose_name_plural = 'carritos'

    @property
    def total(self):
        """Suma de los subtotales con el precio ACTUAL del catálogo."""
        return sum(item.subtotal for item in self.items.all())

    def __str__(self):
        return f'Carrito de {self.usuario.username}'


class ItemCarrito(models.Model):
    """
    ----------------------------------------------------------------------
    ÍTEM DEL CARRO
    - Relación N:1 con Carrito (related_name='items').
    - UniqueConstraint (carrito, producto): un producto aparece UNA sola
      vez por carro. Si se agrega de nuevo, se suma la cantidad en vez
      de duplicar la fila (validación de duplicados).
    - Agregar al carro NO descuenta stock.
    ----------------------------------------------------------------------
    """
    carrito = models.ForeignKey(
        Carrito,
        on_delete=models.CASCADE,
        related_name='items',
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='items_carrito',
    )
    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ítem de carrito'
        verbose_name_plural = 'ítems de carrito'
        constraints = [
            models.UniqueConstraint(
                fields=['carrito', 'producto'],
                name='unico_producto_por_carrito',
            ),
        ]

    @property
    def subtotal(self):
        return self.producto.precio * self.cantidad

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'