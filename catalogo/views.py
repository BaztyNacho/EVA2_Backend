"""
==========================================================================
 VISTAS DE LA APP: catalogo
 CRUD de categorías y productos mediante ModelViewSet.
 Un ModelViewSet genera automáticamente las acciones:
   list (GET lista), retrieve (GET detalle), create (POST),
   update (PUT), partial_update (PATCH) y destroy (DELETE).
 Permisos (matriz de la pauta):
   - PÚBLICO: GET de productos y categorías (sin token).
   - ADMINISTRADOR: POST / PUT / PATCH / DELETE.
==========================================================================
"""
from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from usuarios.permissions import EsAdministradorOSoloLectura

from .filters import ProductoFilter
from .models import Categoria, Producto
from .serializers import CategoriaSerializer, ProductoSerializer


class CategoriaViewSet(viewsets.ModelViewSet):
    """
    ----------------------------------------------------------------------
    /api/categorias/
    - Búsqueda por nombre: ?search=procesador
    - destroy(): si la categoría tiene productos, la FK con PROTECT lanza
      ProtectedError. Se captura para responder 400 con un mensaje claro
      en lugar de un error 500.
    ----------------------------------------------------------------------
    """
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [EsAdministradorOSoloLectura]
    search_fields = ['nombre']
    ordering_fields = ['nombre']

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'No se puede eliminar una categoría que tiene productos asociados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProductoViewSet(viewsets.ModelViewSet):
    """
    ----------------------------------------------------------------------
    /api/productos/
    - select_related('categoria'): trae la categoría en la MISMA consulta
      SQL (JOIN), evitando una consulta extra por cada producto.
    - filterset_class: filtros de django-filter (ver filters.py).
    - search_fields: búsqueda de texto con ?search=
    - ordering_fields: orden con ?ordering=precio o ?ordering=-precio
    ----------------------------------------------------------------------
    """
    queryset = Producto.objects.select_related('categoria').all()
    serializer_class = ProductoSerializer
    permission_classes = [EsAdministradorOSoloLectura]
    filterset_class = ProductoFilter
    search_fields = ['nombre', 'marca', 'sku', 'descripcion']
    ordering_fields = ['precio', 'nombre', 'stock', 'fecha_creacion']