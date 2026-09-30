"""
==========================================================================
 RUTAS DE LA APP: ordenes  (prefijo /api/)
 Incluye el reporte de ventas del dashboard (/api/reportes/ventas/).
==========================================================================
"""
from django.urls import path

from .reportes import ReporteVentasView
from .views import (
    CambiarEstadoView,
    CheckoutView,
    MisOrdenesView,
    OrdenesAdminView,
    PagarOrdenView,
)

urlpatterns = [
    path('ordenes/', OrdenesAdminView.as_view(), name='ordenes'),
    path('ordenes/checkout/', CheckoutView.as_view(), name='checkout'),
    path('ordenes/<int:pk>/pagar/', PagarOrdenView.as_view(), name='orden-pagar'),
    path('ordenes/<int:pk>/estado/', CambiarEstadoView.as_view(), name='orden-estado'),
    path('mis-ordenes/', MisOrdenesView.as_view(), name='mis-ordenes'),
    path('reportes/ventas/', ReporteVentasView.as_view(), name='reporte-ventas'),
]