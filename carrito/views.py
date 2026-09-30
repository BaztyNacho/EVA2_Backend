"""
==========================================================================
 VISTAS DE LA APP: carrito
 Todas requieren token JWT de un usuario con rol CLIENTE.
 El carro SIEMPRE se obtiene a partir de request.user (el dueño del
 token), nunca de un ID enviado por el cliente: así un usuario jamás
 puede ver ni modificar el carro de otro.
==========================================================================
"""
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import EsCliente

from .models import Carrito, ItemCarrito
from .serializers import (
    ActualizarCantidadSerializer,
    AgregarItemSerializer,
    CarritoSerializer,
)


def obtener_carrito(usuario):
    """
    ----------------------------------------------------------------------
    Retorna el carro del usuario (relación 1 a 1).
    get_or_create es un respaldo: si por algún motivo el usuario no
    tiene carro (por ejemplo, fue creado antes de existir la señal),
    se crea en ese momento.
    ----------------------------------------------------------------------
    """
    carrito, _ = Carrito.objects.get_or_create(usuario=usuario)
    return carrito


def respuesta_carrito(carrito, codigo=status.HTTP_200_OK):
    """
    ----------------------------------------------------------------------
    Serializa el carro completo. prefetch_related + select_related
    cargan ítems y productos en pocas consultas SQL (evita el problema
    N+1: una consulta extra por cada ítem).
    ----------------------------------------------------------------------
    """
    carrito = (
        Carrito.objects
        .prefetch_related('items__producto')
        .get(pk=carrito.pk)
    )
    return Response(CarritoSerializer(carrito).data, status=codigo)


class CarritoView(APIView):
    """
    ----------------------------------------------------------------------
    /api/carro/
      GET    -> ver el carro con sus ítems y total.
      POST   -> agregar un producto (si ya está, SUMA la cantidad).
      DELETE -> vaciar el carro completo.
    ----------------------------------------------------------------------
    """
    permission_classes = [IsAuthenticated, EsCliente]

    @extend_schema(responses=CarritoSerializer)
    def get(self, request):
        return respuesta_carrito(obtener_carrito(request.user))

    @extend_schema(request=AgregarItemSerializer, responses={201: CarritoSerializer})
    def post(self, request):
        serializer = AgregarItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        producto = serializer.validated_data['producto']
        cantidad = serializer.validated_data['cantidad']
        carrito = obtener_carrito(request.user)

        # ------------------------------------------------------------------
        # CONTROL DE DUPLICADOS
        # get_or_create busca el ítem (carrito, producto):
        #   - Si NO existe, lo crea con la cantidad pedida.
        #   - Si YA existe, suma la cantidad con F('cantidad'), que hace la
        #     suma directamente en PostgreSQL (UPDATE ... SET cantidad =
        #     cantidad + X), evitando errores si llegan dos peticiones a
        #     la vez.
        # NO se toca el stock: solo se descuenta al pagar la orden.
        # ------------------------------------------------------------------
        with transaction.atomic():
            item, creado = ItemCarrito.objects.get_or_create(
                carrito=carrito,
                producto=producto,
                defaults={'cantidad': cantidad},
            )
            if not creado:
                item.cantidad = F('cantidad') + cantidad
                item.save(update_fields=['cantidad'])
            carrito.save(update_fields=['fecha_actualizacion'])

        return respuesta_carrito(carrito, status.HTTP_201_CREATED)

    @extend_schema(responses=CarritoSerializer)
    def delete(self, request):
        carrito = obtener_carrito(request.user)
        carrito.items.all().delete()
        carrito.save(update_fields=['fecha_actualizacion'])
        return respuesta_carrito(carrito)


class ItemCarritoView(APIView):
    """
    ----------------------------------------------------------------------
    /api/carro/items/{id}/
      PATCH  -> modificar la cantidad de un ítem.
      DELETE -> eliminar un ítem del carro.
    get_object_or_404 filtra por id Y por carrito__usuario=request.user:
    si el ítem pertenece al carro de otro usuario, responde 404 (como si
    no existiera), sin revelar información ajena.
    ----------------------------------------------------------------------
    """
    permission_classes = [IsAuthenticated, EsCliente]

    def obtener_item(self, request, pk):
        return get_object_or_404(ItemCarrito, pk=pk, carrito__usuario=request.user)

    @extend_schema(request=ActualizarCantidadSerializer, responses=CarritoSerializer)
    def patch(self, request, pk):
        item = self.obtener_item(request, pk)
        serializer = ActualizarCantidadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.cantidad = serializer.validated_data['cantidad']
        item.save(update_fields=['cantidad'])
        item.carrito.save(update_fields=['fecha_actualizacion'])
        return respuesta_carrito(item.carrito)

    @extend_schema(responses=CarritoSerializer)
    def delete(self, request, pk):
        item = self.obtener_item(request, pk)
        carrito = item.carrito
        item.delete()
        carrito.save(update_fields=['fecha_actualizacion'])
        return respuesta_carrito(carrito)