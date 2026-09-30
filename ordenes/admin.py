"""
==========================================================================
 ADMIN DE LA APP: ordenes
 Las órdenes se muestran en /admin/ en modo SOLO LECTURA para el estado
 y los montos: el cambio de estado debe hacerse por la API
 (PATCH /api/ordenes/{id}/estado/), que es donde se ejecuta la lógica
 transaccional de descuento y reposición de stock. Si se editara aquí,
 se saltaría esa lógica.
==========================================================================
"""
from django.contrib import admin

from .models import ItemOrden, Orden


class ItemOrdenInline(admin.TabularInline):
    model = ItemOrden
    extra = 0
    can_delete = False
    readonly_fields = ('producto', 'nombre_producto', 'sku', 'precio_unitario', 'cantidad')


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'usuario', 'estado', 'total', 'fecha_creacion')
    list_filter = ('estado',)
    search_fields = ('codigo', 'usuario__username')
    readonly_fields = (
        'codigo', 'usuario', 'estado', 'total',
        'stock_descontado', 'fecha_creacion', 'fecha_pago',
    )
    inlines = [ItemOrdenInline]