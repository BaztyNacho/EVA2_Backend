"""
==========================================================================
 SEÑALES DE LA APP: carrito
 Una señal (signal) es una función que Django ejecuta automáticamente
 cuando ocurre un evento en un modelo. Aquí se escucha post_save del
 Usuario: justo después de guardar un usuario NUEVO con rol CLIENTE, se
 le crea su carro. Así se cumple la relación 1 a 1 Usuario <-> Carrito
 sin tener que crearlo manualmente en cada registro.
==========================================================================
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Carrito


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_carrito_para_cliente(sender, instance, created, **kwargs):
    """
    ----------------------------------------------------------------------
    - created=True solo en la PRIMERA vez que se guarda el usuario
      (INSERT), no en las actualizaciones posteriores (UPDATE).
    - get_or_create evita duplicar el carro si ya existiera.
    ----------------------------------------------------------------------
    """
    if created and instance.rol == instance.Rol.CLIENTE:
        Carrito.objects.get_or_create(usuario=instance)