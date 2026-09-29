from django.conf import settings
from django.contrib.auth import login, logout
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.services import cart_dto, find_cart, merge_guest_cart
from catalog.dto import product_dto, product_queryset, store_dto
from catalog.models import Product
from core.errors import ApiError

from . import google, otp, password_reset
from .identity import normalize_phone, parse_identifier
from .models import Address, OtpCode, SavedPaymentMethod, User, WishlistItem, default_notification_prefs
from .serializers import (
    AddressSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    NotificationPrefsSerializer,
    OtpSendSerializer,
    OtpVerifySerializer,
    PaymentMethodPatchSerializer,
    PaymentMethodSerializer,
    ProfileSerializer,
    ResetPasswordSerializer,
    SigninSerializer,
    SignupSerializer,
    WishlistSerializer,
)
from .sms import sms_configured


def user_dto(user) -> dict:
    return {
        "id": user.pk,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "createdAt": user.created_at.isoformat(),
        "hasPassword": user.has_usable_password(),
        "google": bool(user.google_sub),
    }


def auth_config() -> dict:
    return {
        "google": google.google_configured(),
        "otp": True,
        "otpDevMode": settings.DEBUG and not sms_configured(),
        "passwordReset": True,
    }


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


def payment_method_dto(m: SavedPaymentMethod) -> dict:
    return {
        "id": m.pk,
        "kind": m.kind,
        "label": m.label or (("Telebirr " + m.phone) if m.kind == "telebirr" else f"{m.brand} •••• {m.last4}"),
        "phone": m.phone or None,
        "brand": m.brand or None,
        "last4": m.last4 or None,
        "expiry": m.expiry or None,
        "holder": m.holder or None,
        "isDefault": m.is_default,
    }


def payment_method_list(user) -> list[dict]:
    return [payment_method_dto(m) for m in SavedPaymentMethod.objects.filter(user=user)]


def _safe_next(value) -> str:
    return value if isinstance(value, str) and value.startswith("/") and not value.startswith("//") else "/account"


def _sign_in(request, user, remember=True):
    login(request, user)
    if not remember:
        request.session.set_expiry(0)  # ends with the browser session
    merge_guest_cart(request, user)


# ── Session ──


class CsrfView(APIView):
    """GET before the first unsafe request: sets the csrftoken cookie."""

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"ok": True})


class AuthConfigView(APIView):
    def get(self, request):
        return Response(auth_config())


class MeView(APIView):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"user": user_dto(request.user) if request.user.is_authenticated else None})

    def patch(self, request):
        if not request.user.is_authenticated:
            raise ApiError("Please sign in first", 401)
        s = ProfileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        user = request.user
        if "name" in data:
            user.name = data["name"]
        if "email" in data:
            email = (data["email"] or "").strip().lower() or None
            if email:
                try:
                    validate_email(email)
                except DjangoValidationError:
                    raise ApiError("Enter a valid email address", 422, "email")
                if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                    raise ApiError("That email is already used by another account", 409, "email")
            user.email = email
        if "phone" in data:
            phone = normalize_phone(data["phone"]) if data["phone"] else None
            if data["phone"] and not phone:
                raise ApiError("Enter a valid phone number, e.g. 0911 234 567", 422, "phone")
            if phone and User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                raise ApiError("That phone number is already used by another account", 409, "phone")
            user.phone = phone
        if not user.email and not user.phone:
            raise ApiError("Keep at least one of email or phone so you can sign in", 422, "email")
        user.save()
        return Response({"user": user_dto(user)})


class ShellView(APIView):
    """Everything a page needs about the visitor: user, cart, saved product ids, store details."""

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response(
            {
                "user": user_dto(user) if user else None,
                "cart": cart_dto(find_cart(request)),
                "wishlist": wishlist_ids(user) if user else [],
                "store": store_dto(),
                "auth": auth_config(),
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
        _sign_in(request, user)
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
        _sign_in(request, user, data["remember"])
        return Response({"user": user_dto(user)})


class SignoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


# ── Phone (OTP) sign-in ──


class OtpSendView(APIView):
    def post(self, request):
        s = OtpSendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        phone = normalize_phone(s.validated_data["phone"])
        if not phone:
            raise ApiError("Enter a valid phone number, e.g. 0911 234 567", 422, "phone")
        info = otp.send_code(phone, OtpCode.Purpose.LOGIN)
        info["phone"] = phone
        info["newAccount"] = not User.objects.filter(phone=phone).exists()
        return Response(info)


class OtpVerifyView(APIView):
    def post(self, request):
        s = OtpVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        phone = normalize_phone(data["phone"])
        if not phone:
            raise ApiError("Enter a valid phone number", 422, "phone")
        user = User.objects.filter(phone=phone).first()
        if not user and len((data.get("name") or "").strip()) < 2:
            raise ApiError("Enter your name to create your account", 422, "name")
        otp.verify_code(phone, OtpCode.Purpose.LOGIN, data["code"])
        created = False
        if not user:
            user = User.objects.create_user(name=data["name"].strip(), phone=phone)
            created = True
        _sign_in(request, user, data["remember"])
        return Response({"user": user_dto(user)}, status=status.HTTP_201_CREATED if created else 200)


# ── Google ──


class GoogleStartView(APIView):
    def get(self, request):
        if not google.google_configured():
            raise ApiError("Google sign-in isn't set up on this server", 503)
        return HttpResponseRedirect(google.start_url(request, _safe_next(request.query_params.get("next"))))


class GoogleCallbackView(APIView):
    def get(self, request):
        next_path = _safe_next(request.session.pop(google.NEXT_KEY, None))
        try:
            user = google.finish(request, request.query_params.get("code", ""), request.query_params.get("state", ""))
        except ApiError:
            return HttpResponseRedirect(f"{settings.FRONTEND_ORIGIN}/signin?error=google&next={next_path}")
        _sign_in(request, user)
        return HttpResponseRedirect(f"{settings.FRONTEND_ORIGIN}{next_path}")


# ── Passwords ──


class ForgotPasswordView(APIView):
    def post(self, request):
        s = ForgotPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ident = parse_identifier(s.validated_data["identifier"])
        if not ident:
            raise ApiError("Enter a valid phone number (09…) or email address", 422, "identifier")
        return Response(password_reset.start_reset(ident))


class ResetPasswordView(APIView):
    def post(self, request):
        s = ResetPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        if data.get("uid"):
            user = password_reset.finish_reset_by_token(data["uid"], data["token"], data["password"])
        else:
            phone = normalize_phone(data["phone"])
            if not phone:
                raise ApiError("Enter a valid phone number", 422, "phone")
            user = password_reset.finish_reset_by_code(phone, data["code"], data["password"])
        _sign_in(request, user)
        return Response({"user": user_dto(user)})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if user.has_usable_password() and not user.check_password(s.validated_data.get("current") or ""):
            raise ApiError("Your current password isn't right", 422, "current")
        user.set_password(s.validated_data["password"])
        user.save(update_fields=["password"])
        login(request, user)  # keep the session after the password change
        return Response({"user": user_dto(user)})


# ── Notifications ──


class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def _prefs(self, user):
        return {**default_notification_prefs(), **(user.notification_prefs or {})}

    def get(self, request):
        return Response(self._prefs(request.user))

    def patch(self, request):
        s = NotificationPrefsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        request.user.notification_prefs = {**self._prefs(request.user), **s.validated_data}
        request.user.save(update_fields=["notification_prefs"])
        return Response(self._prefs(request.user))


# ── Saved payment methods ──


class PaymentMethodListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"methods": payment_method_list(request.user)})

    def post(self, request):
        s = PaymentMethodSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        phone = ""
        if d["kind"] == "telebirr":
            phone = normalize_phone(d["phone"]) or ""
            if not phone:
                raise ApiError("Enter a valid Telebirr phone number", 422, "phone")
        first = not SavedPaymentMethod.objects.filter(user=request.user).exists()
        is_default = first or bool(d.get("isDefault"))
        if is_default:
            SavedPaymentMethod.objects.filter(user=request.user).update(is_default=False)
        SavedPaymentMethod.objects.create(
            user=request.user,
            kind=d["kind"],
            label=d.get("label", ""),
            phone=phone,
            brand=d.get("brand", "") if d["kind"] == "card" else "",
            last4=d.get("last4", "") if d["kind"] == "card" else "",
            expiry=d.get("expiry", "") if d["kind"] == "card" else "",
            holder=d.get("holder", "") if d["kind"] == "card" else "",
            is_default=is_default,
        )
        return Response({"methods": payment_method_list(request.user)}, status=status.HTTP_201_CREATED)


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _own(self, request, pk):
        m = SavedPaymentMethod.objects.filter(pk=pk, user=request.user).first()
        if not m:
            raise ApiError("Payment method not found", 404)
        return m

    def patch(self, request, pk):
        m = self._own(request, pk)
        s = PaymentMethodPatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if "label" in s.validated_data:
            m.label = s.validated_data["label"]
        if s.validated_data.get("isDefault"):
            SavedPaymentMethod.objects.filter(user=request.user).update(is_default=False)
            m.is_default = True
        m.save()
        return Response({"methods": payment_method_list(request.user)})

    def delete(self, request, pk):
        m = self._own(request, pk)
        was_default = m.is_default
        m.delete()
        if was_default:
            nxt = SavedPaymentMethod.objects.filter(user=request.user).order_by("created_at").first()
            if nxt:
                nxt.is_default = True
                nxt.save(update_fields=["is_default"])
        return Response({"methods": payment_method_list(request.user)})


# ── Wishlist ──


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, user):
        rows = WishlistItem.objects.filter(user=user).select_related("product__category", "product__brand").prefetch_related("product__plans", "product__add_ons", "product__variants")
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
