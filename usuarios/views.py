"""
==========================================================================
 VISTAS DE LA APP: usuarios
 Endpoints de autenticación: login, refresh, registro, perfil y logout.
==========================================================================
"""
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    LogoutSerializer,
    RegistroSerializer,
    TokenConRolSerializer,
    UsuarioSerializer,
)


class LoginView(TokenObtainPairView):
    """
    ----------------------------------------------------------------------
    POST /api/auth/login/  (público)
    Recibe username y password. Si son correctos, retorna:
      - access: token de corta duración para consumir la API.
      - refresh: token para renovar el access cuando expire.
      - usuario: datos básicos incluyendo el rol.
    Usa TokenConRolSerializer, que agrega el claim 'rol' al token.
    ----------------------------------------------------------------------
    """
    serializer_class = TokenConRolSerializer


class RegistroView(generics.CreateAPIView):
    """
    ----------------------------------------------------------------------
    POST /api/auth/registro/  (público)
    Crea una nueva cuenta con rol CLIENTE.
    ----------------------------------------------------------------------
    """
    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]


class PerfilView(generics.RetrieveAPIView):
    """
    ----------------------------------------------------------------------
    GET /api/auth/perfil/  (requiere token)
    Retorna los datos del usuario dueño del token.
    ----------------------------------------------------------------------
    """
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    """
    ----------------------------------------------------------------------
    POST /api/auth/logout/  (requiere token)
    Los JWT no se guardan en el servidor, por lo que no se pueden
    "borrar". Para cerrar sesión, el refresh token se agrega a la
    BLACKLIST (tabla token_blacklist_blacklistedtoken): desde ese
    momento ya no sirve para obtener nuevos access tokens.
    El carro NO se toca: sigue guardado en PostgreSQL.
    ----------------------------------------------------------------------
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={205: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except TokenError:
            return Response(
                {'detail': 'El refresh token es inválido o ya fue invalidado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'detail': 'Sesión cerrada correctamente.'},
            status=status.HTTP_205_RESET_CONTENT,
        )