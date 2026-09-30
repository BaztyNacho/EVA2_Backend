"""
==========================================================================
 VISTAS DE LA APP: ordenes
 Matriz de permisos de la pauta:
   CLIENTE:        POST /api/ordenes/checkout/
                   GET  /api/mis-ordenes/
                   POST /api/ordenes/{id}/pagar/   (simulación de pago)
   ADMINISTRADOR:  PATCH /api/ordenes/{id}/estado/
                   GET   /api/ordenes/             (todas las órdenes)
 La lógica de stock NO está aquí: está en services.py.
==========================================================================
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from carrito.models import Carrito
from usuarios.permissions import EsAdministrador, EsCliente

from . import services
from .filters import OrdenFilter
from .models import ItemOrden, Orden
from .serializers import CambiarEstadoSerializer, OrdenSerializer


def respuesta_orden(orden_id, codigo=status.HTTP_200_OK):
    """Retorna la orden serializada con sus ítems (una consulta extra)."""
    orden = Orden.objects.select_related('usuario').prefetch_related('items').get(pk=orden_id)
    return Response(OrdenSerializer(orden).data, status=codigo)


def ejecutar_servicio(funcion, orden_id, *args):
    """
    ----------------------------------------------------------------------
    Ejecuta una función de services.py y traduce sus excepciones a
    respuestas HTTP:
      - TransicionInvalida -> 400 Bad Request
      - StockInsuficiente  -> 409 Conflict (con el detalle por producto)
    ----------------------------------------------------------------------
    """
    try:
        funcion(orden_id, *args)
    except services.TransicionInvalida as error:
        return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
    except services.StockInsuficiente as error:
        return Response(
            {
                'detail': 'Pago rechazado: stock insuficiente. La orden sigue PENDIENTE.',
                'productos': error.detalle,
            },
            status=status.HTTP_409_CONFLICT,
        )
    return respuesta_orden(orden_id)


class CheckoutView(APIView):
    """
    ----------------------------------------------------------------------
    POST /api/ordenes/checkout/  (CLIENTE)
    Convierte el carro en una Orden de Compra:
      1. Bloquea el carro del usuario (evita doble checkout simultáneo).
      2. Si está vacío, responde 400.
      3. Crea la Orden en estado PENDIENTE.
      4. Copia cada ítem a ItemOrden CONGELANDO nombre, SKU y precio.
      5. Calcula y guarda el total.
      6. Vacía el carro (queda listo para la próxima compra).
    Todo dentro de transaction.atomic(): si algo falla, no se crea la
    orden ni se vacía el carro. El stock NO se toca aquí.
    ----------------------------------------------------------------------
    """
    permission_classes = [IsAuthenticated, EsCliente]

    @extend_schema(request=None, responses={201: OrdenSerializer})
    def post(self, request):
        with transaction.atomic():
            carrito, _ = Carrito.objects.select_for_update().get_or_create(usuario=request.user)
            items_carrito = list(carrito.items.select_related('producto'))

            if not items_carrito:
                return Response(
                    {'detail': 'El carro está vacío.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            orden = Orden.objects.create(usuario=request.user)
            items_orden = [
                ItemOrden(
                    orden=orden,
                    producto=item.producto,
                    nombre_producto=item.producto.nombre,
                    sku=item.producto.sku,
                    precio_unitario=item.producto.precio,
                    cantidad=item.cantidad,
                )
                for item in items_carrito
            ]
            ItemOrden.objects.bulk_create(items_orden)

            orden.total = sum(item.subtotal for item in items_orden)
            orden.save(update_fields=['total'])

            carrito.items.all().delete()

        return respuesta_orden(orden.id, status.HTTP_201_CREATED)


class PagarOrdenView(APIView):
    """
    ----------------------------------------------------------------------
    POST /api/ordenes/{id}/pagar/  (CLIENTE)
    Simula la confirmación del pago. Solo el dueño de la orden puede
    pagarla: si la orden es de otro usuario, responde 404.
    ----------------------------------------------------------------------
    """
    permission_classes = [IsAuthenticated, EsCliente]

    @extend_schema(
        request=None,
        responses={
            200: OrdenSerializer,
            400: OpenApiResponse(description='La orden no está PENDIENTE.'),
            409: OpenApiResponse(description='Stock insuficiente: pago rechazado.'),
        },
    )
    def post(self, request, pk):
        orden = get_object_or_404(Orden, pk=pk, usuario=request.user)
        return ejecutar_servicio(services.pagar_orden, orden.id)


class CambiarEstadoView(APIView):
    """
    ----------------------------------------------------------------------
    PATCH /api/ordenes/{id}/estado/  (ADMINISTRADOR)
    Body: {"estado": "PAGADO" | "ENTREGADO" | "CANCELADO"}
    services.cambiar_estado aplica la máquina de estados y la lógica
    de descuento o reposición de stock que corresponda.
    ----------------------------------------------------------------------
    """
    permission_classes = [EsAdministrador]

    @extend_schema(
        request=CambiarEstadoSerializer,
        responses={
            200: OrdenSerializer,
            400: OpenApiResponse(description='Transición de estado no permitida.'),
            409: OpenApiResponse(description='Stock insuficiente al pasar a PAGADO.'),
        },
    )
    def patch(self, request, pk):
        orden = get_object_or_404(Orden, pk=pk)
        serializer = CambiarEstadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return ejecutar_servicio(
            services.cambiar_estado, orden.id, serializer.validated_data['estado']
        )


class MisOrdenesView(generics.ListAPIView):
    """
    ----------------------------------------------------------------------
    GET /api/mis-ordenes/  (CLIENTE)
    Historial de compras del usuario autenticado. El queryset se filtra
    por request.user, así cada cliente ve solo sus órdenes.
    Filtros: ?estado=, ?fecha_desde=, ?fecha_hasta=
    ----------------------------------------------------------------------
    """
    serializer_class = OrdenSerializer
    permission_classes = [IsAuthenticated, EsCliente]
    filterset_class = OrdenFilter
    ordering_fields = ['fecha_creacion', 'total']

    def get_queryset(self):
        return (
            Orden.objects
            .filter(usuario=self.request.user)
            .select_related('usuario')
            .prefetch_related('items')
        )


class OrdenesAdminView(generics.ListAPIView):
    """
    ----------------------------------------------------------------------
    GET /api/ordenes/  (ADMINISTRADOR)
    Todas las órdenes del sistema, para gestionar sus estados.
    Filtros: ?estado=, ?usuario=, ?fecha_desde=, ?fecha_hasta=
    ----------------------------------------------------------------------
    """
    serializer_class = OrdenSerializer
    permission_classes = [EsAdministrador]
    filterset_class = OrdenFilter
    search_fields = ['codigo', 'usuario__username']
    ordering_fields = ['fecha_creacion', 'total', 'estado']

    def get_queryset(self):
        return Orden.objects.select_related('usuario').prefetch_related('items')