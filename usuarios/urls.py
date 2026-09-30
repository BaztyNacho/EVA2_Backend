"""
==========================================================================
 RUTAS DE LA APP: usuarios  (prefijo /api/auth/)
==========================================================================
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, PerfilView, RegistroView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('registro/', RegistroView.as_view(), name='registro'),
    path('perfil/', PerfilView.as_view(), name='perfil'),
    path('logout/', LogoutView.as_view(), name='logout'),
]