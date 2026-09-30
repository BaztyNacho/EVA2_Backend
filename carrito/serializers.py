"""
==========================================================================
 SERIALIZADORES DE LA APP: carrito
 - ItemCarritoSerializer / CarritoSerializer: lectura del carro.
 - AgregarItemSerializer / ActualizarCantidadSerializer: validan los
   datos que envía el cliente al agregar o modificar ítems.
==========================================================================
"""
from rest_framework import serializers

from catalogo.models import Producto

from .models import Carrito, ItemCarrito


class ItemCarritoSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    ÍTEM DEL CARRO (lectura)
    Muestra el precio ACTUAL del catálogo. El precio recién se congela
    al hacer checkout, cuando se copia a ItemOrden.
    producto_imagen: ruta de la foto del producto (o null), para mostrarla
    en el mini-carro lateral sin hacer otra petición a la API.
    ----------------------------------------------------------------------
    """
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_imagen = serializers.ImageField(source='producto.imagen', read_only=True)
    sku = serializers.CharField(source='producto.sku', read_only=True)
    precio_unitario = serializers.IntegerField(source='producto.precio', read_only=True)
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemCarrito
        fields = ('id', 'producto', 'producto_nombre', 'producto_imagen', 'sku', 'precio_unitario', 'cantidad', 'subtotal')


class CarritoSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    CARRO COMPLETO (lectura)
    Incluye los ítems anidados, la cantidad total de unidades y el total
    en CLP calculado con los precios actuales.
    ----------------------------------------------------------------------
    """
    usuario = serializers.CharField(source='usuario.username', read_only=True)
    items = ItemCarritoSerializer(many=True, read_only=True)
    total_unidades = serializers.SerializerMethodField()
    total = serializers.IntegerField(read_only=True)

    class Meta:
        model = Carrito
        fields = ('id', 'usuario', 'items', 'total_unidades', 'total', 'fecha_actualizacion')

    def get_total_unidades(self, carrito) -> int:
        return sum(item.cantidad for item in carrito.items.all())


class AgregarItemSerializer(serializers.Serializer):
    """
    ----------------------------------------------------------------------
    AGREGAR PRODUCTO AL CARRO (escritura)
    - producto: debe existir en el catálogo (PrimaryKeyRelatedField
      valida el ID contra la tabla catalogo_producto).
    - cantidad: entero mayor o igual a 1.
    ----------------------------------------------------------------------
    """
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.IntegerField(min_value=1, default=1)


class ActualizarCantidadSerializer(serializers.Serializer):
    """
    ----------------------------------------------------------------------
    MODIFICAR CANTIDAD DE UN ÍTEM (escritura)
    Reemplaza la cantidad por el nuevo valor (no la suma).
    ----------------------------------------------------------------------
    """
    cantidad = serializers.IntegerField(min_value=1)