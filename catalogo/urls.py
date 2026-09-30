"""
==========================================================================
 RUTAS DE LA APP: catalogo  (prefijo /api/)
 El DefaultRouter crea las rutas del CRUD a partir de cada ViewSet:
   /api/categorias/        -> GET (lista), POST (crear)
   /api/categorias/{id}/   -> GET (detalle), PUT, PATCH, DELETE
   /api/productos/         -> GET (lista), POST (crear)
   /api/productos/{id}/    -> GET (detalle), PUT, PATCH, DELETE
==========================================================================
"""
from rest_framework.routers import DefaultRouter

from .views import CategoriaViewSet, ProductoViewSet

router = DefaultRouter()
router.register('categorias', CategoriaViewSet, basename='categoria')
router.register('productos', ProductoViewSet, basename='producto')

urlpatterns = router.urls