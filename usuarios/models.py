"""
==========================================================================
 MODELOS DE LA APP: usuarios
 Define el usuario personalizado del sistema con su ROL.
==========================================================================
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    ----------------------------------------------------------------------
    USUARIO PERSONALIZADO
    Hereda de AbstractUser (username, password, email, is_staff, etc.)
    y agrega el campo 'rol' con CHOICES.

    Roles del negocio:
      - CLIENTE: explora el catálogo, usa su carro y compra.
      - ADMINISTRADOR: Administrador de TI, gestiona categorías,
        productos y cambia el estado de las órdenes.

    El rol viaja como claim dentro del token JWT (ver serializers.py).
    ----------------------------------------------------------------------
    """

    # ------------------------------------------------------------------
    # CHOICES del rol: el valor guardado en la BD y su etiqueta legible.
    # ------------------------------------------------------------------
    class Rol(models.TextChoices):
        CLIENTE = 'CLIENTE', 'Cliente'
        ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador de TI'

    rol = models.CharField(
        max_length=15,
        choices=Rol.choices,
        default=Rol.CLIENTE,
    )
    email = models.EmailField(unique=True)

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def save(self, *args, **kwargs):
        """
        ------------------------------------------------------------------
        SINCRONIZACIÓN ROL <-> is_staff
        1. Un superusuario (createsuperuser) siempre es ADMINISTRADOR.
        2. is_staff se deriva del rol: solo los ADMINISTRADOR son staff.
        Esto permite usar el permiso nativo IsAdminUser de DRF (que
        revisa is_staff) y que siempre sea coherente con el rol.
        ------------------------------------------------------------------
        """
        if self.is_superuser:
            self.rol = self.Rol.ADMINISTRADOR
        self.is_staff = self.rol == self.Rol.ADMINISTRADOR
        super().save(*args, **kwargs)

    @property
    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    def __str__(self):
        return f'{self.username} ({self.get_rol_display()})'