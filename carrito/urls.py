"""
==========================================================================
 RUTAS DE LA APP: carrito  (prefijo /api/)
   /api/carro/               -> GET, POST, DELETE
   /api/carro/items/{id}/    -> PATCH, DELETE
==========================================================================
"""
from django.urls import path

from .views import CarritoView, ItemCarritoView

urlpatterns = [
    path('carro/', CarritoView.as_view(), name='carro'),
    path('carro/items/<int:pk>/', ItemCarritoView.as_view(), name='carro-item'),
]