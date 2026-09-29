from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.services import get_or_create_cart
from core.errors import ApiError

from .serializers import CheckoutSerializer, ExtendSerializer
from .services import extend_rental, get_order, list_orders, place_order


class CheckoutView(APIView):
    """Places the order from the current cart. Payment is simulated (see orders/services.py)."""

    def post(self, request):
        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        cart = get_or_create_cart(request)
        order = place_order(cart.id, user, s.validated_data)
        return Response({"orderId": str(order.id), "number": order.number}, status=status.HTTP_201_CREATED)


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


class ExtendRentalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        s = ExtendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(extend_rental(pk, request.user, s.validated_data["days"]))
