"""
==========================================================================
 ADMIN DE LA APP: usuarios
 Registra el usuario personalizado en el panel /admin/ agregando el
 campo 'rol' a los formularios de edición y de creación.
==========================================================================
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Rol en la tienda', {'fields': ('rol',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol en la tienda', {'fields': ('email', 'rol')}),
    )
    list_display = ('username', 'email', 'rol', 'is_staff', 'is_active')
    list_filter = ('rol', 'is_active')