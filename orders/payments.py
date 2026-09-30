"""
Taking payment for an order.

With CHAPA_SECRET_KEY set, Telebirr and card orders are paid on Chapa's hosted page (which offers
Telebirr, CBE Birr and cards): `start_payment` returns the page URL, Chapa sends the customer back
to `/api/payments/return` and (independently) calls `/api/payments/webhook`, and we confirm the
transaction with Chapa before marking the order paid.

Without a key the API is in development mode: those orders are marked paid straight away.
Pay-on-delivery orders stay pending until the driver collects.
"""

import hashlib
import hmac
import logging

import requests
from django.conf import settings
from django.utils import timezone

from core.errors import ApiError

from .models import Order, PaymentMethod, PaymentStatus

log = logging.getLogger(__name__)

CHAPA_API = "https://api.chapa.co/v1"


def chapa_configured() -> bool:
    return bool(settings.CHAPA_SECRET_KEY)


def provider_name() -> str:
    return "chapa" if chapa_configured() else "simulated"


def _mark_paid(order: Order):
    if order.payment_status != PaymentStatus.PAID:
        order.payment_status = PaymentStatus.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=["payment_status", "paid_at"])


def settle_new_order(order: Order) -> dict:
    """Called right after an order is created. Returns the `payment` block for the checkout response."""
    if order.payment_method == PaymentMethod.COD:
        order.payment_provider = "cod"
        order.save(update_fields=["payment_provider"])
        return {"status": "pending", "method": "cod"}
    if not chapa_configured():
        order.payment_provider = "simulated"
        order.save(update_fields=["payment_provider"])
        _mark_paid(order)
        return {"status": "paid", "method": order.payment_method.lower(), "simulated": True}
    return {"status": "pending", "method": order.payment_method.lower(), "redirectUrl": start_payment(order)}


def start_payment(order: Order) -> str:
    """Creates (or re-creates) a Chapa transaction for a pending order and returns its checkout URL."""
    if not chapa_configured():
        raise ApiError("Online payment isn't set up on this server", 503)
    if order.payment_status == PaymentStatus.PAID:
        raise ApiError("This order is already paid")
    tx_ref = f"{order.number}-{timezone.now().strftime('%H%M%S')}"
    first, _, last = order.contact_name.partition(" ")
    payload = {
        "amount": str(order.total),
        "currency": "ETB",
        "email": order.contact_email,
        "first_name": first or "Customer",
        "last_name": last or "-",
        "phone_number": order.payment_phone or order.contact_phone,
        "tx_ref": tx_ref,
        "callback_url": f"{settings.API_PUBLIC_URL}/api/payments/webhook",
        "return_url": f"{settings.API_PUBLIC_URL}/api/payments/return?tx_ref={tx_ref}",
        "customization": {"title": "Simbatech", "description": f"Order {order.number}"},
    }
    res = requests.post(f"{CHAPA_API}/transaction/initialize", json=payload, headers={"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}, timeout=20)
    data = res.json() if res.content else {}
    if not res.ok or data.get("status") != "success":
        log.error("Chapa initialize failed for %s: %s", order.number, data)
        raise ApiError("We couldn't start the payment. Please try again.", 502)
    order.payment_provider = "chapa"
    order.payment_ref = tx_ref
    order.save(update_fields=["payment_provider", "payment_ref"])
    return data["data"]["checkout_url"]


def verify_payment(tx_ref: str) -> Order | None:
    """Asks Chapa whether the transaction succeeded and updates the order. Returns the order."""
    order = Order.objects.filter(payment_ref=tx_ref).first()
    if not order:
        return None
    if order.payment_status == PaymentStatus.PAID:
        return order
    res = requests.get(f"{CHAPA_API}/transaction/verify/{tx_ref}", headers={"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}, timeout=20)
    data = res.json() if res.content else {}
    status = (data.get("data") or {}).get("status")
    if res.ok and data.get("status") == "success" and status == "success":
        _mark_paid(order)
    elif status in ("failed", "cancelled"):
        order.payment_status = PaymentStatus.FAILED
        order.save(update_fields=["payment_status"])
    return order


def webhook_signature_ok(request) -> bool:
    """
    Chapa sends two headers, both HMAC-SHA256 keyed with the webhook "Secret hash":
    `x-chapa-signature` signs the request body, `Chapa-Signature` signs the secret itself.
    Either one matching is enough. (The payment is still confirmed with Chapa's verify API
    before an order is marked paid, so a forged webhook can't mark anything paid.)
    """
    secret = settings.CHAPA_WEBHOOK_SECRET
    if not secret:
        return False
    key = secret.encode()
    of_body = hmac.new(key, request.body, hashlib.sha256).hexdigest()
    of_secret = hmac.new(key, key, hashlib.sha256).hexdigest()
    x_sig = request.headers.get("x-chapa-signature", "")
    chapa_sig = request.headers.get("Chapa-Signature", "")
    return (bool(x_sig) and hmac.compare_digest(x_sig, of_body)) or (
        bool(chapa_sig) and (hmac.compare_digest(chapa_sig, of_secret) or hmac.compare_digest(chapa_sig, of_body))
    )
