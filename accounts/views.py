from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.services import cart_dto, find_cart, merge_guest_cart
from catalog.dto import product_dto, product_queryset
from catalog.models import Product
from core.errors import ApiError

from .identity import normalize_phone, parse_identifier
from .models import Address, User, WishlistItem
from .serializers import AddressSerializer, SigninSerializer, SignupSerializer, WishlistSerializer


def user_dto(user) -> dict:
    return {"id": user.pk, "name": user.name, "email": user.email, "phone": user.phone, "createdAt": user.created_at.isoformat()}


def wishlist_ids(user) -> list[str]:
    return list(WishlistItem.objects.filter(user=user).values_list("product__slug", flat=True))


def address_dto(a: Address) -> dict:
    return {
        "id": a.pk,
        "label": a.label,
        "line1": a.line1,
        "area": a.area,
        "city": a.city,
        "phone": a.phone,
        "notes": a.notes or None,
        "isDefault": a.is_default,
        "createdAt": a.created_at.isoformat(),
    }


def address_list(user) -> list[dict]:
    return [address_dto(a) for a in Address.objects.filter(user=user)]


# ── Session ──


class CsrfView(APIView):
    """GET before the first unsafe request: sets the csrftoken cookie."""

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"ok": True})


class MeView(APIView):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"user": user_dto(request.user) if request.user.is_authenticated else None})


class ShellView(APIView):
    """Everything a page needs about the visitor: user, cart and saved product ids."""

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response(
            {
                "user": user_dto(user) if user else None,
                "cart": cart_dto(find_cart(request)),
                "wishlist": wishlist_ids(user) if user else [],
            }
        )


class SignupView(APIView):
    def post(self, request):
        s = SignupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        ident = parse_identifier(data["identifier"])
        if not ident:
            raise ApiError("Enter a valid phone number (09…) or email address", 422, "identifier")
        if User.objects.filter(**ident).exists():
            raise ApiError("An account already exists with that " + ("email" if "email" in ident else "phone number"), 409, "identifier")
        user = User.objects.create_user(name=data["name"], password=data["password"], **ident)
        login(request, user)
        merge_guest_cart(request, user)
        return Response({"user": user_dto(user)}, status=status.HTTP_201_CREATED)


WRONG = "That phone/email and password don't match"


class SigninView(APIView):
    def post(self, request):
        s = SigninSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        ident = parse_identifier(data["identifier"])
        user = User.objects.filter(**ident).first() if ident else None
        if not user or not user.is_active or not user.check_password(data["password"]):
            raise ApiError(WRONG, 401)
        login(request, user)
        if not data["remember"]:
            request.session.set_expiry(0)  # ends with the browser session
        merge_guest_cart(request, user)
        return Response({"user": user_dto(user)})


class SignoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


# ── Wishlist ──


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, user):
        rows = WishlistItem.objects.filter(user=user).select_related("product__category", "product__brand").prefetch_related("product__plans", "product__add_ons")
        return {"items": [product_dto(r.product) for r in rows], "ids": [r.product.slug for r in rows]}

    def get(self, request):
        return Response(self._payload(request.user))

    def post(self, request):
        s = WishlistSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        product = Product.objects.filter(slug=s.validated_data["productId"]).first()
        if not product:
            raise ApiError("Product not found", 404)
        if s.validated_data["saved"]:
            WishlistItem.objects.get_or_create(user=request.user, product=product)
        else:
            WishlistItem.objects.filter(user=request.user, product=product).delete()
        return Response(self._payload(request.user))


# ── Addresses ──


def _clean_address(data: dict, current_phone: str | None = None) -> dict:
    phone = normalize_phone(data["phone"]) if "phone" in data else current_phone
    if not phone:
        raise ApiError("Enter a valid phone number", 422, "phone")
    fields = {k: v for k, v in data.items() if k in ("label", "line1", "area", "city", "notes")}
    fields["phone"] = phone
    return fields


class AddressListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"addresses": address_list(request.user)})

    def post(self, request):
        s = AddressSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        fields = _clean_address(s.validated_data)
        first = not Address.objects.filter(user=request.user).exists()
        is_default = first or bool(s.validated_data.get("isDefault"))
        if is_default:
            Address.objects.filter(user=request.user).update(is_default=False)
        Address.objects.create(user=request.user, is_default=is_default, **fields)
        return Response({"addresses": address_list(request.user)}, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _own(self, request, pk):
        address = Address.objects.filter(pk=pk, user=request.user).first()
        if not address:
            raise ApiError("Address not found", 404)
        return address

    def patch(self, request, pk):
        address = self._own(request, pk)
        s = AddressSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        fields = _clean_address(s.validated_data, address.phone)
        if s.validated_data.get("isDefault"):
            Address.objects.filter(user=request.user).update(is_default=False)
            fields["is_default"] = True
        for k, v in fields.items():
            setattr(address, k, v)
        address.save()
        return Response({"addresses": address_list(request.user)})

    def delete(self, request, pk):
        address = self._own(request, pk)
        was_default = address.is_default
        address.delete()
        if was_default:
            nxt = Address.objects.filter(user=request.user).order_by("created_at").first()
            if nxt:
                nxt.is_default = True
                nxt.save(update_fields=["is_default"])
        return Response({"addresses": address_list(request.user)})
