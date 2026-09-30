"""
==========================================================================
 PERMISOS PERSONALIZADOS (RBAC - Control de acceso basado en roles)
 Se reutilizan en todas las apps (catalogo, carrito, ordenes).
 DRF llama a has_permission() antes de ejecutar la vista: si retorna
 False, responde 401 (sin token) o 403 (token válido pero sin permiso).
==========================================================================
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class EsAdministrador(BasePermission):
    """
    ----------------------------------------------------------------------
    Solo usuarios autenticados con rol ADMINISTRADOR.
    Se usa en la gestión de inventario y en el cambio de estado de
    órdenes. request.user lo carga JWTAuthentication a partir del
    'user_id' que viene dentro del token.
    ----------------------------------------------------------------------
    """
    message = 'Solo un Administrador de TI puede realizar esta acción.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.es_administrador
        )


class EsAdministradorOSoloLectura(BasePermission):
    """
    ----------------------------------------------------------------------
    Catálogo público:
    - Métodos de lectura (GET, HEAD, OPTIONS): cualquiera, sin token.
    - Métodos de escritura (POST, PUT, PATCH, DELETE): solo ADMINISTRADOR.
    ----------------------------------------------------------------------
    """
    message = 'Solo un Administrador de TI puede modificar el catálogo.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.es_administrador
        )


class EsCliente(BasePermission):
    """
    ----------------------------------------------------------------------
    Solo usuarios autenticados con rol CLIENTE (carro y compras).
    ----------------------------------------------------------------------
    """
    message = 'Esta acción está disponible solo para clientes.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol == request.user.Rol.CLIENTE
        )