"""
==========================================================================
 CONFIGURACIÓN PRINCIPAL DEL PROYECTO: tienda_hardware
 Tienda de Hardware y Componentes PC (Retail) - EVA 2 Desarrollo Backend
 Alumno: Bastian Ignacio Sandoval Reyes | Sección: AP-N4-C2 | Año: 2026
==========================================================================
 Los datos sensibles (SECRET_KEY y credenciales de PostgreSQL) NO se
 escriben aquí: se leen desde el archivo .env mediante python-decouple,
 para que nunca queden publicados en GitHub.
==========================================================================
"""
from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# SEGURIDAD BÁSICA
# SECRET_KEY firma las sesiones y también los tokens JWT (algoritmo HS256).
# --------------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']


# --------------------------------------------------------------------------
# APLICACIONES INSTALADAS
# Bloque 1: apps nativas de Django.
# Bloque 2: librerías de terceros (API REST, JWT, filtros y Swagger).
# Bloque 3: apps propias del proyecto, una por cada dominio del negocio.
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  # Permite invalidar refresh tokens (logout)
    'django_filters',
    'drf_spectacular',

    'usuarios',   # Usuario personalizado con rol (Cliente / Administrador)
    'catalogo',   # Categorías y productos (inventario)
    'carrito',    # Carro de compras persistente (1 a 1 con el usuario)
    'ordenes',    # Órdenes de compra, estados y lógica de stock
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tienda_hardware.urls'

# --------------------------------------------------------------------------
# PLANTILLAS HTML
# DIRS apunta a la carpeta /templates de la raíz (base.html con el footer).
# El context processor 'datos_alumno' inyecta nombre, sección y año en
# TODAS las plantillas, así el footer no se repite en cada vista.
# --------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tienda_hardware.context_processors.datos_alumno',
            ],
        },
    },
]

WSGI_APPLICATION = 'tienda_hardware.wsgi.application'


# --------------------------------------------------------------------------
# BASE DE DATOS: PostgreSQL (requisito de la pauta, no se usa SQLite)
# Motor nativo 'django.db.backends.postgresql' con el driver psycopg.
# Las credenciales vienen del archivo .env.
# --------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}


# --------------------------------------------------------------------------
# MODELO DE USUARIO PERSONALIZADO
# Reemplaza al User de Django por usuarios.Usuario, que agrega el campo 'rol'.
# IMPORTANTE: debe definirse ANTES de la primera migración.
# --------------------------------------------------------------------------
AUTH_USER_MODEL = 'usuarios.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --------------------------------------------------------------------------
# INTERNACIONALIZACIÓN (Chile)
# --------------------------------------------------------------------------
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS (CSS y JavaScript de la interfaz de la tienda)
# STATICFILES_DIRS indica la carpeta /static de la raíz del proyecto.
# En las plantillas se cargan con {% load static %} y {% static '...' %}.
# --------------------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# --------------------------------------------------------------------------
# ARCHIVOS SUBIDOS (MEDIA): fotos de productos cargadas desde el panel.
# Se guardan en la carpeta /media de la raíz y se sirven en /media/...
# (en desarrollo los entrega Django; ver urls.py).
# --------------------------------------------------------------------------
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --------------------------------------------------------------------------
# DJANGO REST FRAMEWORK
# - Autenticación: JWT (header "Authorization: Bearer <access_token>").
# - Permiso por defecto: IsAuthenticated. Las vistas públicas (catálogo)
#   lo sobrescriben explícitamente con AllowAny.
# - Filtros globales: django-filter, búsqueda por texto y ordenamiento.
# - Esquema: drf-spectacular genera el OpenAPI para Swagger.
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


# --------------------------------------------------------------------------
# JWT (SimpleJWT) - TTL de los tokens
# - Access token: 5 minutos. Se envía en cada petición. Coincide con el
#   cierre por inactividad de la tienda (static/js/sesion.js).
# - Refresh token: 10 minutos. Solo sirve para pedir un nuevo access.
#   Tiene 5 minutos de margen para que "Seguir conectado" funcione
#   durante la cuenta regresiva del aviso, y es el límite que impone el
#   servidor: ningún token sirve más de 10 minutos sin renovarse.
# - Rotación + blacklist: cada vez que se usa un refresh se entrega uno
#   nuevo y el anterior queda invalidado (no se puede reutilizar).
# --------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=10),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# --------------------------------------------------------------------------
# SWAGGER / OPENAPI (drf-spectacular)
# --------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'API Tienda de Hardware y Componentes PC',
    'DESCRIPTION': (
        'EVA 2 Desarrollo Backend - Bastian Ignacio Sandoval Reyes - '
        'Sección AP-N4-C2 - 2026'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}


# --------------------------------------------------------------------------
# SESIONES DE DJANGO
# La tienda y la API usan JWT; la sesión de Django solo la usan el panel
# /admin/ y la documentación /api/docs/. Para que un navegador no quede
# con acceso abierto por días (por defecto duran 2 semanas):
# - SESSION_COOKIE_AGE: la sesión vence tras 5 minutos (igual que la
#   inactividad permitida en la tienda)...
# - SESSION_SAVE_EVERY_REQUEST: ...contados desde la ÚLTIMA actividad.
# - SESSION_EXPIRE_AT_BROWSER_CLOSE: también se cierra al cerrar el
#   navegador.
# --------------------------------------------------------------------------
SESSION_COOKIE_AGE = 5 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# --------------------------------------------------------------------------
# DOCUMENTACIÓN DE LA API SOLO PARA EL SUPERUSUARIO
# True: /api/docs/ y /api/schema/ exigen la sesión del admin de Django.
# False: la documentación es pública. Se configura en el archivo .env.
# --------------------------------------------------------------------------
DOCS_SOLO_ADMIN = config('DOCS_SOLO_ADMIN', default=True, cast=bool)


# --------------------------------------------------------------------------
# DATOS DEL ALUMNO (se muestran en el footer de las vistas HTML)
# --------------------------------------------------------------------------
DATOS_ALUMNO = {
    'nombre': 'Bastian Ignacio Sandoval Reyes',
    'seccion': 'AP-N4-C2',
    'anio': 2026,
}