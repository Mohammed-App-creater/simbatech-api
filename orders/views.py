from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.identity import normalize_phone
from cart.services import get_or_create_cart
from core.errors import ApiError

from . import payments
from .models import Order
from .serializers import CheckoutSerializer, ExtendSerializer, StartPaymentSerializer
from .services import extend_rental, get_order, list_orders, place_order, track_order


class CheckoutView(APIView):
    """Places the order from the current cart, then starts payment (see orders/payments.py)."""

    def post(self, request):
        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        cart = get_or_create_cart(request)
        order = place_order(cart.id, user, s.validated_data)
        payment = payments.settle_new_order(order)
        return Response({"orderId": str(order.id), "number": order.number, "payment": payment}, status=status.HTTP_201_CREATED)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"orders": list_orders(request.user)})


class OrderDetailView(APIView):
    def get(self, request, pk):
        order = get_order(pk, request.user if request.user.is_authenticated else None)
        if not order:
            raise ApiError("Order not found", 404)
        return Response(order)


class TrackOrderView(APIView):
    """GET /api/orders/track?number=ST-123456&phone=09... — no sign-in needed."""

    def get(self, request):
        number = (request.query_params.get("number") or "").strip()
        phone = normalize_phone(request.query_params.get("phone"))
        if not number or not phone:
            raise ApiError("Enter your order number and the phone number used on the order", 422)
        order = track_order(number, phone)
        if not order:
            raise ApiError("We couldn't find an order with that number and phone", 404)
        return Response(order)


class ExtendRentalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        s = ExtendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(extend_rental(pk, request.user, s.validated_data["days"]))


# ── Payments ──


class StartPaymentView(APIView):
    """POST {orderId}: (re)start online payment for an unpaid order. Returns {redirectUrl}."""

    def post(self, request):
        s = StartPaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        dto = get_order(s.validated_data["orderId"], user)
        if not dto:
            raise ApiError("Order not found", 404)
        order = Order.objects.get(id=dto["id"])
        return Response({"redirectUrl": payments.start_payment(order)})


class PaymentReturnView(APIView):
    """Where the gateway sends the customer after paying. Confirms the payment, then shows the order."""

    def get(self, request):
        tx_ref = request.query_params.get("tx_ref") or request.query_params.get("trx_ref") or ""
        order = payments.verify_payment(tx_ref) if tx_ref else None
        if not order:
            return HttpResponseRedirect(f"{settings.FRONTEND_ORIGIN}/account")
        result = "paid" if order.payment_status == "PAID" else "failed"
        return HttpResponseRedirect(f"{settings.FRONTEND_ORIGIN}/order-confirmed/{order.id}?payment={result}")


class PaymentWebhookView(APIView):
    """Chapa calls this when a transaction settles, even if the customer closed the page."""

    def post(self, request):
        if not payments.webhook_signature_ok(request):
            raise ApiError("Bad signature", 403)
        tx_ref = (request.data or {}).get("tx_ref") or (request.data or {}).get("trx_ref") or ""
        if tx_ref:
            payments.verify_payment(tx_ref)
        return Response({"ok": True})
