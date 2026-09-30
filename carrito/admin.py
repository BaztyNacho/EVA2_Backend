"""
==========================================================================
 ADMIN DE LA APP: carrito
 Permite revisar desde /admin/ que el carro y sus ítems persisten en
 PostgreSQL (útil para demostrarlo en la defensa).
==========================================================================
"""
from django.contrib import admin

from .models import Carrito, ItemCarrito


class ItemCarritoInline(admin.TabularInline):
    model = ItemCarrito
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha_actualizacion')
    inlines = [ItemCarritoInline]