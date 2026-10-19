"""
==========================================================================
 MIDDLEWARE: BloqueoNavegacionAdmin
 --------------------------------------------------------------------------
 Protege las rutas internas del sistema. Solo el SUPERUSUARIO, con su
 sesión de Django abierta, puede verlas:
   - /admin/  (admin de Django, incluido su formulario de login): se
              bloquea SIEMPRE para cualquier otro, ya sea navegando o
              desde una herramienta como Postman o curl.
   - /api/... (API navegable de DRF y documentación Swagger): se bloquea
              solo cuando alguien la ABRE en el navegador, porque la
              propia tienda consume la API con JavaScript.

 ¿Cómo distingue una "navegación" de una petición de la tienda?
 El navegador agrega a cada petición el header Sec-Fetch-Mode:
   - 'navigate'  -> alguien escribió la URL o hizo clic en un enlace.
                    ESTO es lo que se bloquea.
   - 'cors' / 'same-origin' -> el JavaScript de la tienda (fetch) pide
                    datos a la API. Esto NO se bloquea: la tienda sigue
                    funcionando y la API aplica sus permisos JWT de siempre.
 Si el navegador no envía ese header (navegadores antiguos), se considera
 navegación cuando la petición acepta HTML (Accept: text/html).
 En /api/, Postman, curl y otros clientes de API no se bloquean.

 Respuesta: 204 No Content. Cuando el navegador recibe un 204 al
 navegar, NO cambia de página: el usuario se queda donde estaba, sin
 error ni redirección.

 El superusuario abre su sesión de Django desde la tienda con
 POST /api/auth/sesion-admin/ (ver usuarios/views.py), que llama el
 JavaScript de la barra de administrador antes de navegar.
 Este middleware debe ir DESPUÉS de AuthenticationMiddleware en
 settings.py, porque usa request.user (el usuario de la sesión).
==========================================================================
"""
from django.conf import settings
from django.http import HttpResponse

RUTA_ADMIN = '/admin/'
RUTA_API = '/api/'
RUTAS_DOCUMENTACION = ('/api/docs/', '/api/schema/')


def es_navegacion(request):
    """True si el usuario abrió la URL en el navegador (no un fetch)."""
    modo = request.headers.get('Sec-Fetch-Mode')
    if modo:
        return modo == 'navigate'
    return 'text/html' in request.headers.get('Accept', '')


class BloqueoNavegacionAdmin:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ruta = request.path
        usuario = request.user
        es_superusuario = usuario.is_authenticated and usuario.is_superuser

        if not es_superusuario:
            # 1. Admin de Django: bloqueado siempre para cualquier otro
            if ruta.startswith(RUTA_ADMIN):
                return HttpResponse(status=204)

            # 2. API: bloqueada solo al abrirla en el navegador. Con
            #    DOCS_SOLO_ADMIN=False la documentación vuelve a ser pública.
            docs_publica = (not getattr(settings, 'DOCS_SOLO_ADMIN', True)
                            and ruta.startswith(RUTAS_DOCUMENTACION))
            if ruta.startswith(RUTA_API) and not docs_publica and es_navegacion(request):
                return HttpResponse(status=204)

        return self.get_response(request)