"""
==========================================================================
 SERIALIZADORES DE LA APP: catalogo
 Convierten Categoria y Producto a JSON (lectura) y validan los datos
 recibidos al crear o editar (escritura).
==========================================================================
"""
from rest_framework import serializers

from .models import Categoria, Producto


class CategoriaSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    CATEGORÍA
    total_productos: campo calculado (solo lectura) que cuenta cuántos
    productos pertenecen a la categoría usando la relación inversa
    'productos' (related_name de la FK en Producto).
    ----------------------------------------------------------------------
    """
    total_productos = serializers.IntegerField(source='productos.count', read_only=True)

    class Meta:
        model = Categoria
        fields = ('id', 'nombre', 'descripcion', 'total_productos')


class ProductoSerializer(serializers.ModelSerializer):
    """
    ----------------------------------------------------------------------
    PRODUCTO
    - categoria: se recibe como ID al crear/editar (FK).
    - categoria_nombre: solo lectura, para mostrar el nombre en el JSON
      sin tener que hacer otra consulta desde el cliente.
    - imagen: opcional. Al leer, DRF entrega la URL completa de la foto
      (o null si no tiene). Al escribir, se envía como archivo en un
      formulario multipart/form-data (no en JSON).
    - quitar_imagen: solo escritura. Si llega en true, se elimina la
      foto actual del producto.
    - validate_precio(): el precio debe ser mayor a 0.
    - validate_imagen(): la foto debe ser JPG, PNG o WebP y no puede pesar
      más de 2 MB. Además, el ImageField de DRF usa Pillow para comprobar
      que el archivo sea realmente una imagen (no solo por su nombre).
    ----------------------------------------------------------------------
    """
    TAMANO_MAXIMO_IMAGEN = 2 * 1024 * 1024  # 2 MB en bytes
    EXTENSIONES_PERMITIDAS = ('jpg', 'jpeg', 'png', 'webp')

    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    imagen = serializers.ImageField(required=False, allow_null=True)
    quitar_imagen = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Producto
        fields = (
            'id', 'nombre', 'marca', 'precio', 'sku', 'descripcion', 'stock',
            'imagen', 'quitar_imagen', 'categoria', 'categoria_nombre',
            'fecha_creacion', 'fecha_actualizacion',
        )
        read_only_fields = ('id', 'fecha_creacion', 'fecha_actualizacion')

    def validate_precio(self, valor):
        if valor <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return valor

    def validate_imagen(self, archivo):
        if not archivo:
            return archivo
        extension = archivo.name.rsplit('.', 1)[-1].lower()
        if extension not in self.EXTENSIONES_PERMITIDAS:
            raise serializers.ValidationError('Formato no permitido. Usa JPG, PNG o WebP.')
        if archivo.size > self.TAMANO_MAXIMO_IMAGEN:
            raise serializers.ValidationError('La imagen no puede pesar más de 2 MB.')
        return archivo

    def create(self, validated_data):
        validated_data.pop('quitar_imagen', False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        ------------------------------------------------------------------
        Manejo de la foto al editar:
        - Si llega una imagen nueva, se borra el archivo anterior.
        - Si llega quitar_imagen=true (sin imagen nueva), se borra el
          archivo y el campo queda vacío.
        - Si no llega nada, la foto actual se mantiene.
        ------------------------------------------------------------------
        """
        quitar = validated_data.pop('quitar_imagen', False)
        nueva_imagen = validated_data.get('imagen')

        if (quitar or nueva_imagen) and instance.imagen:
            instance.imagen.delete(save=False)
        if quitar and not nueva_imagen:
            validated_data['imagen'] = None

        return super().update(instance, validated_data)