"""
==========================================================================
 REPORTE DE VENTAS (dashboard del administrador)
 GET /api/reportes/ventas/?dias=30      (dias: 7, 30, 90 o 0 = todo)
 --------------------------------------------------------------------------
 Criterios del reporte:
 - VENTA = orden PAGADA o ENTREGADA (son las que generaron ingreso). Se
   ubican en el tiempo por su fecha_pago.
 - Las PENDIENTES se informan como "por cobrar" y las CANCELADAS se
   usan para la tasa de cancelación; ambas por su fecha_creacion.
 - Cada indicador se compara con el período anterior de igual duración
   (ej: últimos 30 días vs. los 30 días previos).
 Todas las sumas, conteos y agrupaciones se calculan en PostgreSQL con
 el ORM de Django (aggregate, annotate, values, Sum, Count, F, TruncDate),
 no recorriendo registros en Python.
==========================================================================
"""
from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogo.models import Producto
from usuarios.permissions import EsAdministrador

from .models import ItemOrden, Orden

ESTADOS_VENTA = [Orden.Estado.PAGADO, Orden.Estado.ENTREGADO]
PERIODOS_VALIDOS = (7, 30, 90, 0)


def variacion(actual, anterior):
    """Variación porcentual entre dos períodos (None si no hay base)."""
    if not anterior:
        return None
    return round((actual - anterior) * 100 / anterior, 1)


def resumen_ventas(ventas):
    """
    ----------------------------------------------------------------------
    Indicadores de un conjunto de ventas:
    - aggregate() devuelve un solo diccionario con la suma de 'total' y
      el conteo de órdenes (SELECT SUM(total), COUNT(id) ...).
    - Las unidades se suman desde ItemOrden, filtrando por esas órdenes.
    - Coalesce(..., 0) evita None cuando no hay filas.
    ----------------------------------------------------------------------
    """
    datos = ventas.aggregate(ingresos=Coalesce(Sum('total'), 0), ordenes=Count('id'))
    unidades = ItemOrden.objects.filter(orden__in=ventas).aggregate(
        total=Coalesce(Sum('cantidad'), 0)
    )['total']
    ticket = round(datos['ingresos'] / datos['ordenes']) if datos['ordenes'] else 0
    return {'ingresos': datos['ingresos'], 'ordenes': datos['ordenes'], 'ticket': ticket, 'unidades': unidades}


def tasa_cancelacion(ordenes):
    """Porcentaje de órdenes canceladas sobre las creadas en el período."""
    total = ordenes.count()
    canceladas = ordenes.filter(estado=Orden.Estado.CANCELADO).count()
    return round(canceladas * 100 / total, 1) if total else 0


class ReporteVentasView(APIView):
    """
    ----------------------------------------------------------------------
    GET /api/reportes/ventas/?dias=30  (solo ADMINISTRADOR)
    Retorna en un solo JSON todo lo que muestra el dashboard.
    ----------------------------------------------------------------------
    """
    permission_classes = [EsAdministrador]

    @extend_schema(
        parameters=[OpenApiParameter('dias', int, description='Período: 7, 30, 90 o 0 (todo el historial). Por defecto 30.')],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        # ------------------------------------------------------------------
        # 1. PERÍODO ACTUAL Y PERÍODO ANTERIOR
        # ------------------------------------------------------------------
        try:
            dias = int(request.query_params.get('dias', 30))
        except ValueError:
            dias = 30
        if dias not in PERIODOS_VALIDOS:
            dias = 30

        ahora = timezone.now()
        todas_las_ventas = Orden.objects.filter(estado__in=ESTADOS_VENTA)
        todas_las_ordenes = Orden.objects.all()

        if dias:
            inicio = ahora - timedelta(days=dias)
            inicio_anterior = inicio - timedelta(days=dias)
            ventas = todas_las_ventas.filter(fecha_pago__gte=inicio)
            ventas_anteriores = todas_las_ventas.filter(fecha_pago__gte=inicio_anterior, fecha_pago__lt=inicio)
            ordenes = todas_las_ordenes.filter(fecha_creacion__gte=inicio)
            ordenes_anteriores = todas_las_ordenes.filter(fecha_creacion__gte=inicio_anterior, fecha_creacion__lt=inicio)
        else:
            inicio = None
            ventas, ordenes = todas_las_ventas, todas_las_ordenes
            ventas_anteriores = ordenes_anteriores = None

        # ------------------------------------------------------------------
        # 2. INDICADORES PRINCIPALES (con variación vs. período anterior)
        # ------------------------------------------------------------------
        actual = resumen_ventas(ventas)
        cancelacion = tasa_cancelacion(ordenes)
        por_cobrar = ordenes.filter(estado=Orden.Estado.PENDIENTE).aggregate(
            monto=Coalesce(Sum('total'), 0), cantidad=Count('id')
        )
        if ventas_anteriores is not None:
            anterior = resumen_ventas(ventas_anteriores)
            cancelacion_anterior = tasa_cancelacion(ordenes_anteriores)
            variaciones = {clave: variacion(actual[clave], anterior[clave]) for clave in actual}
            variaciones['cancelacion'] = round(cancelacion - cancelacion_anterior, 1) if ordenes_anteriores.exists() else None
        else:
            variaciones = {clave: None for clave in ('ingresos', 'ordenes', 'ticket', 'unidades', 'cancelacion')}

        indicadores = {
            **actual,
            'tasa_cancelacion': cancelacion,
            'por_cobrar': por_cobrar['monto'],
            'ordenes_pendientes': por_cobrar['cantidad'],
            'variaciones': variaciones,
        }

        # ------------------------------------------------------------------
        # 3. INGRESOS POR DÍA
        # TruncDate corta la fecha y hora a solo la fecha (en la zona
        # horaria de Chile) y values().annotate() agrupa por ese día:
        #   SELECT DATE(fecha_pago), SUM(total), COUNT(id) ... GROUP BY 1
        # Luego se completan con 0 los días sin ventas, para que la línea
        # del gráfico sea continua.
        # ------------------------------------------------------------------
        por_dia = {
            fila['dia']: fila
            for fila in ventas.annotate(dia=TruncDate('fecha_pago'))
            .values('dia')
            .annotate(ingresos=Sum('total'), ordenes=Count('id'))
            .order_by('dia')
        }
        ingresos_por_dia = []
        if por_dia or inicio:
            hoy = timezone.localdate()
            dia = timezone.localtime(inicio).date() if inicio else min(por_dia)
            while dia <= hoy:
                fila = por_dia.get(dia, {})
                ingresos_por_dia.append({
                    'fecha': dia.isoformat(),
                    'ingresos': fila.get('ingresos', 0),
                    'ordenes': fila.get('ordenes', 0),
                })
                dia += timedelta(days=1)

        # ------------------------------------------------------------------
        # 4. AGRUPACIONES SOBRE LOS ÍTEMS VENDIDOS
        # El ingreso de cada ítem es precio_unitario (congelado) x cantidad.
        # F() permite multiplicar dos columnas dentro de la consulta SQL.
        # ------------------------------------------------------------------
        items = ItemOrden.objects.filter(orden__in=ventas)
        ingreso_item = Sum(F('precio_unitario') * F('cantidad'))

        por_categoria = [
            {'categoria': fila['categoria'] or 'Producto eliminado', 'ingresos': fila['ingresos'], 'unidades': fila['unidades']}
            for fila in items.values(categoria=F('producto__categoria__nombre'))
            .annotate(ingresos=ingreso_item, unidades=Sum('cantidad'))
            .order_by('-ingresos')
        ]

        top_productos = list(
            items.values('nombre_producto', 'sku')
            .annotate(unidades=Sum('cantidad'), ingresos=ingreso_item)
            .order_by('-unidades', '-ingresos')[:5]
        )

        por_marca = [
            {'marca': fila['marca'] or 'Producto eliminado', 'ingresos': fila['ingresos']}
            for fila in items.values(marca=F('producto__marca'))
            .annotate(ingresos=ingreso_item)
            .order_by('-ingresos')[:8]
        ]

        # ------------------------------------------------------------------
        # 5. ÓRDENES POR ESTADO (todas las creadas en el período)
        # ------------------------------------------------------------------
        conteo_estados = dict(ordenes.values_list('estado').annotate(total=Count('id')))
        por_estado = [
            {'estado': valor, 'etiqueta': etiqueta, 'cantidad': conteo_estados.get(valor, 0)}
            for valor, etiqueta in Orden.Estado.choices
        ]

        # ------------------------------------------------------------------
        # 6. MEJORES CLIENTES (por monto total comprado)
        # ------------------------------------------------------------------
        mejores_clientes = list(
            ventas.values(cliente=F('usuario__username'))
            .annotate(compras=Count('id'), total=Sum('total'))
            .order_by('-total')[:5]
        )

        # ------------------------------------------------------------------
        # 7. STOCK CRÍTICO: productos con 5 unidades o menos que además se
        #    vendieron en el período (candidatos a reponer).
        #    Sum(..., filter=Q(...)) suma solo los ítems de esas ventas.
        # ------------------------------------------------------------------
        stock_critico = list(
            Producto.objects.filter(stock__lte=5)
            .annotate(vendidas=Sum('items_orden__cantidad', filter=Q(items_orden__orden__in=ventas)))
            .filter(vendidas__gt=0)
            .order_by('stock', '-vendidas')
            .values('id', 'nombre', 'sku', 'stock', 'vendidas')[:8]
        )

        # ------------------------------------------------------------------
        # 8. ÚLTIMAS VENTAS
        # ------------------------------------------------------------------
        ultimas_ventas = [
            {
                'id': orden.id,
                'codigo': str(orden.codigo),
                'cliente': orden.usuario.username,
                'total': orden.total,
                'estado': orden.estado,
                'estado_display': orden.get_estado_display(),
                'fecha_pago': orden.fecha_pago,
            }
            for orden in ventas.select_related('usuario').order_by('-fecha_pago')[:6]
        ]

        return Response({
            'periodo': {'dias': dias, 'desde': inicio, 'hasta': ahora},
            'indicadores': indicadores,
            'ingresos_por_dia': ingresos_por_dia,
            'por_categoria': por_categoria,
            'top_productos': top_productos,
            'por_marca': por_marca,
            'por_estado': por_estado,
            'mejores_clientes': mejores_clientes,
            'stock_critico': stock_critico,
            'ultimas_ventas': ultimas_ventas,
        })