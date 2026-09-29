from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import PromoCode
from core.errors import ApiError

from .models import CartItem, Mode
from .serializers import AddBundleSerializer, AddToCartSerializer, PromoSerializer, UpdateCartItemSerializer
from .services import add_bundle, add_to_cart, cart_dto, cart_dto_by_id, find_cart, get_or_create_cart


class CartView(APIView):
    def get(self, request):
        return Response(cart_dto(find_cart(request)))

    def post(self, request):
        """Add a product (buy) or book a rental. Returns the updated cart."""
        s = AddToCartSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cart = get_or_create_cart(request)
        add_to_cart(cart, s.validated_data)
        return Response(cart_dto_by_id(cart.id))


class BundleView(APIView):
    def post(self, request):
        """Book every product in a rental bundle. Returns the updated cart."""
        s = AddBundleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cart = get_or_create_cart(request)
        added = add_bundle(cart, s.validated_data)
        return Response({**cart_dto_by_id(cart.id), "added": added})


class CartItemView(APIView):
    def _own_item(self, request, pk):
        cart = get_or_create_cart(request)
        item = CartItem.objects.filter(pk=pk, cart=cart).first()
        if not item:
            raise ApiError("That item is no longer in your cart", 404)
        return cart, item

    def patch(self, request, pk):
        s = UpdateCartItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        cart, item = self._own_item(request, pk)
        if "qty" in data and item.mode == Mode.BUY:
            item.qty = data["qty"]
        if "rentStart" in data:
            item.rent_start = data["rentStart"]
        if "rentDays" in data:
            item.rent_days = data["rentDays"]
        if "addOns" in data:
            item.add_on_keys = data["addOns"]
        if "savedForLater" in data:
            item.saved_for_later = data["savedForLater"]
        item.save()
        return Response(cart_dto_by_id(cart.id))

    def delete(self, request, pk):
        cart, item = self._own_item(request, pk)
        item.delete()
        return Response(cart_dto_by_id(cart.id))


class PromoView(APIView):
    def post(self, request):
        s = PromoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        promo = PromoCode.objects.filter(code=s.validated_data["code"].strip().upper(), active=True).first()
        if not promo:
            raise ApiError("That code isn't valid", 422, "code")
        cart = get_or_create_cart(request)
        cart.promo_code = promo.code
        cart.save(update_fields=["promo_code"])
        return Response(cart_dto_by_id(cart.id))

    def delete(self, request):
        cart = get_or_create_cart(request)
        cart.promo_code = ""
        cart.save(update_fields=["promo_code"])
        return Response(cart_dto_by_id(cart.id))
