"""
==========================================================================
 CONTEXT PROCESSOR: datos_alumno
 Lee DATOS_ALUMNO desde settings.py y lo deja disponible en todas las
 plantillas como la variable {{ alumno }}. Así el footer de base.html
 muestra nombre, sección y año sin pasarlos manualmente en cada vista.
==========================================================================
"""
from django.conf import settings


def datos_alumno(request):
    return {'alumno': settings.DATOS_ALUMNO}