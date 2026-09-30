"""
==========================================================================
 RUTAS PRINCIPALES DEL PROYECTO: tienda_hardware
 Cada app tiene su propio urls.py y aquí se incluyen con su prefijo.
 Django revisa las rutas EN ORDEN, de arriba hacia abajo, y usa la
 primera que coincide. Por eso el re_path comodín va AL FINAL.
==========================================================================
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from .documentacion import EsquemaProtegidoView, SwaggerProtegidoView
from .views import (
    catalogo,
    detalle_producto,
    inicio,
    pagina_carro,
    pagina_login,
    pagina_mis_ordenes,
    pagina_panel,
    pagina_registro,
    pagina_ventas,
    ruta_no_encontrada,
)


# --------------------------------------------------------------------------
# ADMIN DE DJANGO: solo el SUPERUSUARIO puede entrar.
# Por defecto Django deja entrar a cualquier usuario con is_staff=True;
# aquí se exige además is_superuser. Así, otros usuarios con rol
# ADMINISTRADOR pueden usar el panel de la tienda (/panel/), pero no el
# admin interno de Django.
# --------------------------------------------------------------------------
def solo_superusuario(request):
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = solo_superusuario
admin.site.site_header = 'Tienda de Hardware · Administración'
admin.site.site_title = 'Administración | Tienda de Hardware'
admin.site.index_title = 'Gestión interna'

urlpatterns = [
    # --------------------------------------------------------------
    # Páginas HTML de la tienda (Bootstrap + JavaScript que consume
    # la API con JWT)
    # --------------------------------------------------------------
    path('', inicio, name='inicio'),
    path('login/', pagina_login, name='pagina-login'),
    path('registro/', pagina_registro, name='pagina-registro'),
    path('catalogo/', catalogo, name='pagina-catalogo'),
    path('producto/<int:pk>/', detalle_producto, name='pagina-producto'),
    path('carro/', pagina_carro, name='pagina-carro'),
    path('mis-ordenes/', pagina_mis_ordenes, name='pagina-mis-ordenes'),
    path('panel/', pagina_panel, name='pagina-panel'),
    path('ventas/', pagina_ventas, name='pagina-ventas'),

    # --------------------------------------------------------------
    # Panel de administración de Django (solo superusuario)
    # --------------------------------------------------------------
    path('admin/', admin.site.urls),

    # --------------------------------------------------------------
    # Autenticación JWT: login, refresh, registro, perfil y logout
    # --------------------------------------------------------------
    path('api/auth/', include('usuarios.urls')),

    # --------------------------------------------------------------
    # Catálogo: /api/categorias/ y /api/productos/
    # --------------------------------------------------------------
    path('api/', include('catalogo.urls')),

    # --------------------------------------------------------------
    # Carro de compras persistente: /api/carro/
    # --------------------------------------------------------------
    path('api/', include('carrito.urls')),

    # --------------------------------------------------------------
    # Órdenes: checkout, pago, cambio de estado, historial y reportes
    # --------------------------------------------------------------
    path('api/', include('ordenes.urls')),

    # --------------------------------------------------------------
    # Documentación OpenAPI / Swagger (drf-spectacular)
    # /api/schema/ -> esquema OpenAPI en formato YAML
    # /api/docs/   -> Swagger UI (plantilla propia con footer)
    # Ambas protegidas: solo superusuario (ver documentacion.py).
    # --------------------------------------------------------------
    path('api/schema/', EsquemaProtegidoView.as_view(), name='schema'),
    path(
        'api/docs/',
        SwaggerProtegidoView.as_view(url_name='schema', template_name='swagger_ui.html'),
        name='swagger-ui',
    ),
]

# --------------------------------------------------------------------------
# ARCHIVOS SUBIDOS (fotos de productos) en /media/
# static() solo agrega esta ruta cuando DEBUG=True (desarrollo). Se agrega
# ANTES del re_path comodín; si fuera después, el comodín capturaría
# /media/... y las fotos responderían 404.
# --------------------------------------------------------------------------
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    # --------------------------------------------------------------
    # RE_PATH COMODÍN (debe ir SIEMPRE al final)
    # La expresión regular ^.*$ coincide con CUALQUIER ruta. Como
    # Django usa la primera coincidencia, solo llegan aquí las URLs
    # que no calzaron con ninguna ruta anterior (ej: /HOLA).
    # --------------------------------------------------------------
    re_path(r'^.*$', ruta_no_encontrada, name='ruta-no-encontrada'),
]

# --------------------------------------------------------------------------
# handler404: vista usada cuando otra vista lanza Http404 y DEBUG=False.
# --------------------------------------------------------------------------
handler404 = ruta_no_encontrada