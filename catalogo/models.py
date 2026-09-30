"""
==========================================================================
 MODELOS DE LA APP: catalogo
 Inventario de la tienda: Categorías (Procesadores, Tarjetas de Video,
 RAM, etc.) y Productos con su stock físico disponible.
==========================================================================
"""
from django.core.validators import FileExtensionValidator
from django.db import models


class Categoria(models.Model):
    """
    ----------------------------------------------------------------------
    CATEGORÍA
    Agrupa los productos. Relación 1:N -> una categoría tiene muchos
    productos (related_name='productos').
    ----------------------------------------------------------------------
    """
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """
    ----------------------------------------------------------------------
    PRODUCTO (componente de PC)
    - categoria: FK con on_delete=PROTECT -> no se puede borrar una
      categoría que todavía tenga productos (integridad referencial).
    - sku: código único de inventario.
    - precio: en pesos chilenos (CLP), sin decimales.
    - stock: PositiveIntegerField -> la BD nunca acepta stock negativo.
      El stock SOLO se descuenta cuando una orden pasa a PAGADO.
    - imagen: foto opcional (requiere Pillow). El archivo se guarda en
      MEDIA_ROOT/productos/ y en la base de datos solo queda su ruta.
      Solo se aceptan extensiones jpg, jpeg, png y webp.
    ----------------------------------------------------------------------
    """
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='productos',
    )
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=80)
    precio = models.PositiveIntegerField(help_text='Precio unitario en CLP')
    sku = models.CharField('código SKU', max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(
        upload_to='productos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        help_text='Foto del producto (JPG, PNG o WebP, máximo 2 MB)',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        ordering = ['nombre']

    def delete(self, *args, **kwargs):
        """
        ------------------------------------------------------------------
        Al eliminar el producto se borra también su archivo de imagen,
        para no dejar fotos huérfanas en la carpeta media. Primero se
        elimina el registro y después el archivo: si el borrado en la
        base de datos fallara, la foto no se pierde.
        ------------------------------------------------------------------
        """
        imagen = self.imagen
        resultado = super().delete(*args, **kwargs)
        if imagen:
            imagen.storage.delete(imagen.name)
        return resultado

    def __str__(self):
        return f'{self.nombre} [{self.sku}]'