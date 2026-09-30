"""
==========================================================================
 SERIALIZADORES DE LA APP: usuarios
 Convierten los datos de usuario entre JSON y objetos Python, y
 personalizan el contenido (claims) de los tokens JWT.
==========================================================================
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

Usuario = get_user_model()


class TokenConRolSerializer(TokenObtainPairSerializer):
    """
    ----------------------------------------------------------------------
    LOGIN JWT CON CLAIMS PERSONALIZADOS
    1. get_token(): agrega al payload del token los claims 'username',
       'email' y 'rol'. Se agregan al REFRESH token y SimpleJWT los copia
       automáticamente al ACCESS token, así que ambos llevan el rol
       (también los access tokens generados después con /refresh/).
    2. validate(): además de los tokens 'access' y 'refresh', la
       respuesta del login incluye los datos básicos del usuario.
    ----------------------------------------------------------------------
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['rol'] = user.rol
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'rol': self.user.rol,
        }
        return data


class RegistroSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    REGISTRO DE NUEVOS CLIENTES
    - password y password2 son de solo escritura (nunca se devuelven).
    - Se valida que ambas contraseñas coincidan y que cumplan las reglas
      de AUTH_PASSWORD_VALIDATORS de settings.py.
    - El rol NO se recibe desde el request: todo registro público se
      crea como CLIENTE. Así nadie puede auto-asignarse ADMINISTRADOR.
    - create_user() guarda la contraseña encriptada (hash).
    ----------------------------------------------------------------------
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label='Confirmar contraseña')

    class Meta:
        model = Usuario
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password', 'password2', 'rol')
        read_only_fields = ('id', 'rol')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        return Usuario.objects.create_user(
            rol=Usuario.Rol.CLIENTE,
            **validated_data,
        )


class UsuarioSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    DATOS DEL USUARIO AUTENTICADO (perfil)
    Solo lectura: muestra quién es el dueño del token.
    ----------------------------------------------------------------------
    """
    class Meta:
        model = Usuario
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'rol')
        read_only_fields = fields


class LogoutSerializer(serializers.Serializer):
    """
    ----------------------------------------------------------------------
    LOGOUT
    Recibe el refresh token que se quiere invalidar.
    ----------------------------------------------------------------------
    """
    refresh = serializers.CharField()