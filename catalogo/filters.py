"""
==========================================================================
 FILTROS DE LA APP: catalogo  (django-filter)
 Permiten filtrar el listado de productos con parámetros en la URL.
 Ejemplos:
   /api/productos/?categoria=1
   /api/productos/?categoria_nombre=ram
   /api/productos/?marca=nvidia
   /api/productos/?precio_min=100000&precio_max=500000
   /api/productos/?con_stock=true
 Se pueden combinar entre sí y con ?search= y ?ordering=.
==========================================================================
"""
import django_filters

from .models import Producto


class ProductoFilter(django_filters.FilterSet):
    """
    ----------------------------------------------------------------------
    FILTROS DE PRODUCTO
    - categoria: ID exacto de la categoría.
    - categoria_nombre: nombre de la categoría, sin distinguir mayúsculas
      y aceptando coincidencias parciales (icontains).
    - marca: coincidencia parcial sin distinguir mayúsculas.
    - precio_min / precio_max: rango de precios (gte = mayor o igual,
      lte = menor o igual).
    - con_stock: true -> solo productos con stock > 0.
    ----------------------------------------------------------------------
    """
    categoria_nombre = django_filters.CharFilter(
        field_name='categoria__nombre', lookup_expr='icontains',
    )
    marca = django_filters.CharFilter(lookup_expr='icontains')
    precio_min = django_filters.NumberFilter(field_name='precio', lookup_expr='gte')
    precio_max = django_filters.NumberFilter(field_name='precio', lookup_expr='lte')
    con_stock = django_filters.BooleanFilter(method='filtrar_con_stock')

    class Meta:
        model = Producto
        fields = ['categoria', 'categoria_nombre', 'marca', 'precio_min', 'precio_max', 'con_stock']

    def filtrar_con_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset.filter(stock=0)