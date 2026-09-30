"""
==========================================================================
 DOCUMENTACIÓN DE LA API (Swagger / OpenAPI) SOLO PARA EL SUPERUSUARIO
 --------------------------------------------------------------------------
 Swagger se abre navegando directamente a /api/docs/, sin token JWT, por
 lo que la protección se hace con la SESIÓN de Django (la misma del
 panel /admin/):
   - Si el usuario de la sesión es superusuario -> se muestra Swagger.
   - Si no -> se redirige al login del admin de Django con ?next=, para
     volver a la documentación después de ingresar.
 El control se activa o desactiva con DOCS_SOLO_ADMIN en el archivo .env
 (True por defecto). Con False, la documentación vuelve a ser pública.
 Nota: la documentación solo DESCRIBE los endpoints; la seguridad de los
 datos está en los permisos JWT por rol de cada endpoint.
==========================================================================
"""
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


class SoloSuperusuarioMixin:
    """
    ----------------------------------------------------------------------
    Revisa el usuario ANTES de ejecutar la vista (método dispatch).
    request.user viene de la sesión de Django (AuthenticationMiddleware),
    no del token JWT.
    ----------------------------------------------------------------------
    """

    def dispatch(self, request, *args, **kwargs):
        protegida = getattr(settings, 'DOCS_SOLO_ADMIN', True)
        es_superusuario = request.user.is_authenticated and request.user.is_superuser
        if protegida and not es_superusuario:
            return redirect_to_login(request.get_full_path(), login_url='admin:login')
        return super().dispatch(request, *args, **kwargs)


class EsquemaProtegidoView(SoloSuperusuarioMixin, SpectacularAPIView):
    """GET /api/schema/ -> esquema OpenAPI (YAML), solo superusuario."""


class SwaggerProtegidoView(SoloSuperusuarioMixin, SpectacularSwaggerView):
    """GET /api/docs/ -> interfaz Swagger UI, solo superusuario."""