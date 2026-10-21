"""
==========================================================================
 SERVICIO DE PAGO: Transbank Webpay Plus  (app: ordenes)
 Aquí está TODA la comunicación con Transbank. Las vistas solo llaman a
 estas funciones, igual que con services.py.

 Flujo de un pago:
   1. iniciar_pago(): revisa la orden y el stock, crea la transacción en
      Transbank (create) y guarda el token. Devuelve la URL de Webpay.
   2. El cliente paga en el formulario de Webpay (fuera de la tienda).
   3. Webpay devuelve al cliente a nuestra URL de retorno con el token.
   4. confirmar_pago(): confirma con Transbank (commit). Si el pago fue
      AUTORIZADO, llama a services.pagar_orden(), que descuenta el stock
      de forma atómica. Si justo ahí falta stock, el pago se ANULA
      (refund) para no cobrar algo que no se puede entregar.
   5. abortar_pago(): el cliente canceló en Webpay o se acabó el tiempo.

 Ambiente: INTEGRACIÓN (pruebas). Tarjeta de prueba VISA:
   4051 8856 0044 6623 | CVV 123 | cualquier fecha futura
   RUT 11.111.111-1 | clave 123
==========================================================================
"""
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
from transbank.error.transbank_error import TransbankError
from transbank.webpay.webpay_plus.transaction import Transaction

from catalogo.models import Producto

from . import services
from .models import Orden, TransaccionWebpay

# Segundos máximos de espera por una respuesta de Transbank.
# (El SDK trae 600 por defecto: demasiado para una tienda).
TIEMPO_ESPERA = 30


# --------------------------------------------------------------------------
# EXCEPCIÓN DE NEGOCIO
# --------------------------------------------------------------------------
class ErrorWebpay(Exception):
    """Transbank no respondió o rechazó la operación (create)."""


def _mensaje(error):
    """Texto legible de un error del SDK (TransbankError trae .message)."""
    return getattr(error, 'message', None) or str(error)


def _cliente_transbank():
    """
    ----------------------------------------------------------------------
    Crea el objeto Transaction del SDK con las credenciales de settings.
    TEST = ambiente de integración; LIVE = producción.
    ----------------------------------------------------------------------
    """
    tipo = (
        IntegrationType.LIVE
        if settings.TRANSBANK_AMBIENTE == 'PRODUCCION'
        else IntegrationType.TEST
    )
    opciones = WebpayOptions(
        settings.TRANSBANK_CODIGO_COMERCIO,
        settings.TRANSBANK_API_KEY,
        tipo,
        TIEMPO_ESPERA,
    )
    return Transaction(opciones)


def productos_sin_stock(orden):
    """
    ----------------------------------------------------------------------
    Revisión PREVIA del stock, antes de enviar al cliente a Webpay.
    Así no se le cobra algo que ya se agotó. Retorna la lista de
    productos con problema (vacía si todo está bien).
    La validación DEFINITIVA (con bloqueo de filas) la hace
    services.pagar_orden() al confirmar el pago.
    ----------------------------------------------------------------------
    """
    items = list(orden.items.all())
    stock = dict(
        Producto.objects
        .filter(id__in=[item.producto_id for item in items if item.producto_id])
        .values_list('id', 'stock')
    )
    faltantes = []
    for item in items:
        disponible = stock.get(item.producto_id)
        if disponible is None:
            faltantes.append({
                'producto': item.nombre_producto,
                'motivo': 'El producto ya no existe en el catálogo.',
            })
        elif disponible < item.cantidad:
            faltantes.append({
                'producto': item.nombre_producto,
                'solicitado': item.cantidad,
                'disponible': disponible,
            })
    return faltantes


def iniciar_pago(orden, url_retorno):
    """
    ----------------------------------------------------------------------
    Crea la transacción en Transbank para una orden PENDIENTE.
    - orden_compra (buy_order): "O<id>T<fecha-hora>", máx. 26 caracteres
      y distinto en cada intento.
    - sesion (session_id): id del cliente dueño de la orden.
    Retorna (url, token): el navegador debe enviar token_ws a esa url.
    Lanza TransicionInvalida, StockInsuficiente o ErrorWebpay.
    ----------------------------------------------------------------------
    """
    if orden.estado != Orden.Estado.PENDIENTE:
        raise services.TransicionInvalida('Solo se pueden pagar órdenes PENDIENTES.')

    faltantes = productos_sin_stock(orden)
    if faltantes:
        raise services.StockInsuficiente(faltantes)

    orden_compra = f'O{orden.id}T{timezone.now():%y%m%d%H%M%S}'
    try:
        respuesta = _cliente_transbank().create(
            orden_compra, str(orden.usuario_id), orden.total, url_retorno
        )
    except (TransbankError, requests.RequestException) as error:
        raise ErrorWebpay(f'No se pudo iniciar el pago con Webpay: {_mensaje(error)}') from error

    TransaccionWebpay.objects.create(
        orden=orden,
        token=respuesta['token'],
        orden_compra=orden_compra,
        monto=orden.total,
    )
    return respuesta['url'], respuesta['token']


def _anular(cliente, registro, motivo):
    """
    ----------------------------------------------------------------------
    Devuelve el dinero de un pago ya autorizado (refund por el total).
    Se usa cuando Transbank aprobó, pero la orden no se puede pagar
    (sin stock o la orden ya no estaba PENDIENTE).
    ----------------------------------------------------------------------
    """
    try:
        cliente.refund(registro.token, registro.monto)
        registro.estado = TransaccionWebpay.Estado.ANULADA
        registro.detalle = f'{motivo} Pago devuelto automáticamente.'
    except (TransbankError, requests.RequestException) as error:
        registro.estado = TransaccionWebpay.Estado.ERROR
        registro.detalle = f'{motivo} No se pudo anular: {_mensaje(error)}. Requiere anulación manual.'


def confirmar_pago(token):
    """
    ----------------------------------------------------------------------
    Confirma (commit) el pago cuando el cliente vuelve desde Webpay.
    - select_for_update() bloquea el registro: si el cliente recarga la
      página, el segundo intento espera y luego ve que ya no está
      INICIADA, así el pago no se confirma dos veces.
    - AUTHORIZED + response_code 0 -> services.pagar_orden() (descuenta
      stock). Si falla por stock o estado -> se anula el cobro.
    - Cualquier otra respuesta -> RECHAZADA (la orden sigue PENDIENTE).
    Retorna el registro TransaccionWebpay actualizado, o None si el
    token no pertenece a la tienda.
    ----------------------------------------------------------------------
    """
    with transaction.atomic():
        registro = (
            TransaccionWebpay.objects
            .select_for_update()
            .select_related('orden')
            .filter(token=token)
            .first()
        )
        if registro is None or registro.estado != TransaccionWebpay.Estado.INICIADA:
            return registro

        cliente = _cliente_transbank()
        try:
            respuesta = cliente.commit(token)
        except (TransbankError, requests.RequestException) as error:
            registro.estado = TransaccionWebpay.Estado.ERROR
            registro.detalle = f'Error al confirmar con Transbank: {_mensaje(error)}'[:255]
            registro.save()
            return registro

        # Datos del comprobante que entrega Transbank
        registro.codigo_respuesta = respuesta.get('response_code')
        registro.codigo_autorizacion = respuesta.get('authorization_code') or ''
        registro.ultimos_digitos = ((respuesta.get('card_detail') or {}).get('card_number') or '')[-4:]
        registro.tipo_pago = respuesta.get('payment_type_code') or ''
        registro.cuotas = respuesta.get('installments_number')

        aprobado = (
            respuesta.get('status') == 'AUTHORIZED'
            and respuesta.get('response_code') == 0
            and respuesta.get('amount') == registro.monto
        )
        if not aprobado:
            registro.estado = TransaccionWebpay.Estado.RECHAZADA
            registro.detalle = 'Transbank rechazó el pago.'
        else:
            try:
                services.pagar_orden(registro.orden_id)
                registro.estado = TransaccionWebpay.Estado.AUTORIZADA
                registro.detalle = 'Pago aprobado. Stock descontado.'
            except services.StockInsuficiente:
                _anular(cliente, registro, 'Stock insuficiente al confirmar.')
            except services.TransicionInvalida:
                _anular(cliente, registro, 'La orden ya no estaba PENDIENTE.')

        registro.detalle = registro.detalle[:255]
        registro.save()
        registro.orden.refresh_from_db()
        return registro


def abortar_pago(token=None, orden_compra=None):
    """
    ----------------------------------------------------------------------
    El cliente presionó "Anular" en Webpay (llega TBK_TOKEN) o se acabó
    el tiempo del formulario (llega solo TBK_ORDEN_COMPRA). No hay cobro:
    se marca el intento como ABORTADA y la orden sigue PENDIENTE.
    ----------------------------------------------------------------------
    """
    pendientes = TransaccionWebpay.objects.filter(estado=TransaccionWebpay.Estado.INICIADA)
    if token:
        registro = pendientes.filter(token=token).select_related('orden').first()
    elif orden_compra:
        registro = pendientes.filter(orden_compra=orden_compra).select_related('orden').first()
    else:
        registro = None

    if registro:
        registro.estado = TransaccionWebpay.Estado.ABORTADA
        registro.detalle = 'El cliente anuló el pago o se agotó el tiempo en Webpay.'
        registro.save(update_fields=['estado', 'detalle', 'fecha_actualizacion'])
    return registro