"""
==========================================================================
 VISTAS HTML DE LA TIENDA (no son parte de la API REST)
 Estas vistas solo entregan la plantilla (el "esqueleto" de la página).
 Los datos los carga el JavaScript de cada página consumiendo la API
 con JWT (static/js/api.js), igual que lo haría cualquier otro cliente.
 - ruta_no_encontrada: responde a cualquier URL inexistente capturada
   por el re_path comodín de urls.py (y también como handler404).
==========================================================================
"""
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve

from catalogo.models import Producto


def inicio(request):
    """GET /  -> portada con carrusel, categorías y destacados."""
    return render(request, 'inicio.html')


def pagina_login(request):
    """GET /login/  -> formulario que consume POST /api/auth/login/."""
    return render(request, 'login.html')


def pagina_registro(request):
    """GET /registro/  -> formulario que consume POST /api/auth/registro/."""
    return render(request, 'registro.html')


def catalogo(request):
    """GET /catalogo/  -> grilla con panel de filtros (django-filter)."""
    return render(request, 'catalogo.html')


def detalle_producto(request, pk):
    """
    ----------------------------------------------------------------------
    GET /producto/<pk>/  -> ficha del producto.
    Se consulta solo el nombre para el <title> de la página; si el
    producto no existe, se responde con la página 404 personalizada.
    ----------------------------------------------------------------------
    """
    producto = Producto.objects.filter(pk=pk).only('id', 'nombre').first()
    if producto is None:
        return ruta_no_encontrada(request)
    return render(request, 'detalle_producto.html', {'producto': producto})


def pagina_carro(request):
    """
    GET /carro/  -> carro del cliente.
    Es una página privada: la protección la hace requerirSesion() en el
    JavaScript, porque la sesión vive en el token JWT del navegador (no en
    una cookie que Django pueda leer). Aunque alguien viera el HTML, la
    API igual exige el token para entregar datos del carro.
    """
    return render(request, 'carro.html')


def pagina_mis_ordenes(request):
    """GET /mis-ordenes/  -> historial de órdenes y pago (página privada)."""
    return render(request, 'mis_ordenes.html')


def pagina_panel(request):
    """
    GET /panel/  -> panel de administración (página privada, solo rol
    ADMINISTRADOR). CRUD de productos y categorías y gestión de estados
    de las órdenes. Los permisos reales los aplica la API en cada petición.
    """
    return render(request, 'panel.html')


def pagina_ventas(request):
    """
    GET /ventas/  -> registro de ventas (dashboard), solo ADMINISTRADOR.
    Los datos vienen de GET /api/reportes/ventas/, que valida el rol.
    """
    return render(request, 'ventas.html')


def ruta_no_encontrada(request, exception=None):
    """
    ----------------------------------------------------------------------
    RESPUESTA PARA RUTAS INEXISTENTES (re_path comodín)
    1. Barra final: como el re_path captura TODAS las URLs, Django ya
       no aplica su redirección automática APPEND_SLASH. Por eso, si la
       ruta no termina en "/" pero con "/" sí existe (ej: /api/productos
       -> /api/productos/), se redirige manualmente. Solo en GET/HEAD,
       porque una redirección pierde el cuerpo de un POST.
    2. Rutas bajo /api/: se responde 404 en JSON, porque quien consume
       una API espera JSON, no una página HTML.
    3. Cualquier otra ruta (ej: /HOLA): página 404 personalizada con el
       footer del alumno y enlaces para volver a la tienda.
    El parámetro 'exception' permite reutilizar esta vista como
    handler404 (se usa cuando DEBUG=False).
    ----------------------------------------------------------------------
    """
    ruta = request.path

    if not ruta.endswith('/') and request.method in ('GET', 'HEAD'):
        try:
            coincidencia = resolve(ruta + '/')
            if coincidencia.url_name != 'ruta-no-encontrada':
                destino = ruta + '/'
                if request.META.get('QUERY_STRING'):
                    destino += '?' + request.META['QUERY_STRING']
                return redirect(destino)
        except Resolver404:
            pass

    if ruta.startswith('/api/'):
        return JsonResponse(
            {'detail': 'El endpoint solicitado no existe.', 'ruta': ruta},
            status=404,
        )

    return render(request, '404.html', {'ruta': ruta}, status=404)