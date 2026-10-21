"""
==========================================================================
 ADMIN DE LA APP: ordenes
 Las órdenes se muestran en /admin/ en modo SOLO LECTURA para el estado
 y los montos: el cambio de estado debe hacerse por la API
 (PATCH /api/ordenes/{id}/estado/), que es donde se ejecuta la lógica
 transaccional de descuento y reposición de stock. Si se editara aquí,
 se saltaría esa lógica.
 Las transacciones Webpay también son SOLO LECTURA: son el registro
 de lo que respondió Transbank y no deben modificarse a mano.
==========================================================================
"""
from django.contrib import admin

from .models import ItemOrden, Orden, TransaccionWebpay


class ItemOrdenInline(admin.TabularInline):
    model = ItemOrden
    extra = 0
    can_delete = False
    readonly_fields = ('producto', 'nombre_producto', 'sku', 'precio_unitario', 'cantidad')


class TransaccionWebpayInline(admin.TabularInline):
    """Muestra los intentos de pago Webpay dentro de cada orden."""
    model = TransaccionWebpay
    extra = 0
    can_delete = False
    fields = ('orden_compra', 'estado', 'monto', 'codigo_autorizacion', 'ultimos_digitos', 'fecha_creacion')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        """Los pagos solo se crean desde la tienda, nunca a mano."""
        return False


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'usuario', 'estado', 'total', 'fecha_creacion')
    list_filter = ('estado',)
    search_fields = ('codigo', 'usuario__username')
    readonly_fields = (
        'codigo', 'usuario', 'estado', 'total',
        'stock_descontado', 'fecha_creacion', 'fecha_pago',
    )
    inlines = [ItemOrdenInline, TransaccionWebpayInline]


@admin.register(TransaccionWebpay)
class TransaccionWebpayAdmin(admin.ModelAdmin):
    """
    ----------------------------------------------------------------------
    Listado de todos los pagos con Webpay, con filtro por estado y
    búsqueda por orden de compra, token o cliente. Solo lectura.
    ----------------------------------------------------------------------
    """
    list_display = (
        'orden_compra', 'orden', 'estado', 'monto',
        'codigo_autorizacion', 'ultimos_digitos', 'fecha_creacion',
    )
    list_filter = ('estado',)
    search_fields = ('orden_compra', 'token', 'orden__usuario__username')

    def has_add_permission(self, request):
        """No se crean pagos desde el admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Permite ver el detalle, pero no modificarlo."""
        return False

    def has_delete_permission(self, request, obj=None):
        """El historial de pagos no se borra."""
        return False