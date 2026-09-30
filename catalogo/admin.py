"""
==========================================================================
 ADMIN DE LA APP: catalogo
 Permite gestionar categorías y productos desde /admin/ (útil para
 cargar datos de prueba rápidamente).
==========================================================================
"""
from django.contrib import admin

from .models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'sku', 'categoria', 'precio', 'stock')
    list_filter = ('categoria', 'marca')
    search_fields = ('nombre', 'marca', 'sku')