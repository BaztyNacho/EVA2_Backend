"""
==========================================================================
 FILTROS DE LA APP: ordenes  (django-filter)
 Ejemplos:
   /api/mis-ordenes/?estado=PAGADO
   /api/ordenes/?estado=PENDIENTE&usuario=baztynacho
   /api/ordenes/?fecha_desde=2026-09-01&fecha_hasta=2026-09-30
==========================================================================
"""
import django_filters

from .models import Orden


class OrdenFilter(django_filters.FilterSet):
    """
    ----------------------------------------------------------------------
    - estado: valor exacto de los CHOICES (el filtro muestra la lista).
    - fecha_desde / fecha_hasta: rango sobre la fecha de creación
      (__date extrae solo la fecha, ignorando la hora).
    - usuario: nombre de usuario (útil para el administrador).
    ----------------------------------------------------------------------
    """
    estado = django_filters.ChoiceFilter(choices=Orden.Estado.choices)
    fecha_desde = django_filters.DateFilter(field_name='fecha_creacion__date', lookup_expr='gte')
    fecha_hasta = django_filters.DateFilter(field_name='fecha_creacion__date', lookup_expr='lte')
    usuario = django_filters.CharFilter(field_name='usuario__username', lookup_expr='iexact')

    class Meta:
        model = Orden
        fields = ['estado', 'fecha_desde', 'fecha_hasta', 'usuario']