"""
==========================================================================
 SERIALIZADORES DE LA APP: ordenes
==========================================================================
"""
from rest_framework import serializers

from .models import ItemOrden, Orden


class ItemOrdenSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    ÍTEM DE LA ORDEN
    precio_unitario es el precio CONGELADO al momento del checkout, no el
    precio actual del catálogo.
    ----------------------------------------------------------------------
    """
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemOrden
        fields = ('id', 'producto', 'nombre_producto', 'sku', 'precio_unitario', 'cantidad', 'subtotal')


class OrdenSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    ORDEN DE COMPRA (solo lectura)
    - estado_display: etiqueta legible del CHOICE (get_estado_display).
    - items: detalle histórico anidado.
    ----------------------------------------------------------------------
    """
    usuario = serializers.CharField(source='usuario.username', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    items = ItemOrdenSerializer(many=True, read_only=True)

    class Meta:
        model = Orden
        fields = (
            'id', 'codigo', 'usuario', 'estado', 'estado_display', 'total',
            'fecha_creacion', 'fecha_pago', 'fecha_actualizacion', 'items',
        )
        read_only_fields = fields


class CambiarEstadoSerializer(serializers.Serializer):
    """
    ----------------------------------------------------------------------
    CAMBIO DE ESTADO (administrador)
    Solo acepta estados de destino válidos. PENDIENTE no está incluido
    porque ninguna orden puede volver a PENDIENTE.
    ----------------------------------------------------------------------
    """
    estado = serializers.ChoiceField(choices=[
        (Orden.Estado.PAGADO, 'Pagado'),
        (Orden.Estado.ENTREGADO, 'Entregado'),
        (Orden.Estado.CANCELADO, 'Cancelado'),
    ])