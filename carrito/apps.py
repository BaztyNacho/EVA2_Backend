"""
==========================================================================
 CONFIGURACIÓN DE LA APP: carrito
 El método ready() se ejecuta cuando Django termina de cargar la app.
 Ahí se importa signals.py para que la señal quede registrada; si no se
 importa, Django nunca "escucha" el evento y el carro no se crea.
==========================================================================
"""
from django.apps import AppConfig


class CarritoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'carrito'

    def ready(self):
        from . import signals  # noqa: F401