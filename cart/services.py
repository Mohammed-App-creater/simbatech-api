"""
Cart logic. A signed-in customer has one cart; a guest's cart id is kept in their session and
merged into their account when they sign in.
"""

from datetime import timedelta

from django.db.models import Prefetch

from catalog.dto import product_dto
from catalog.models import Product, PromoCode
from core.errors import ApiError
from core.pricing import compute_totals, rental_line_price, shop_today

from .models import Cart, CartItem, Mode

CART_SESSION_KEY = "cart_id"


def cart_queryset():
    items = (
        CartItem.objects.select_related("product__category", "product__brand")
        .prefetch_related("product__plans", "product__add_ons")
        .order_by("created_at", "id")
    )
    return Cart.objects.prefetch_related(Prefetch("items", queryset=items))


def _guest_cart(request, cart_id):
    if not cart_id:
        return None
    try:
        return cart_queryset().filter(id=cart_id, user__isnull=True).first()
    except Exception:  # not a valid uuid
        return None


def find_cart(request) -> Cart | None:
    """Read-only lookup: never creates a cart or touches the session."""
    if request.user.is_authenticated:
        return cart_queryset().filter(user=request.user).first()
    return _guest_cart(request, request.session.get(CART_SESSION_KEY))


def get_or_create_cart(request) -> Cart:
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    cart = _guest_cart(request, request.session.get(CART_SESSION_KEY))
    if cart is None:
        cart = Cart.objects.create()
        request.session[CART_SESSION_KEY] = str(cart.id)
    return cart


def merge_guest_cart(request, user):
    """On sign-in / sign-up: move the guest cart's lines into the user's cart."""
    guest_id = request.session.pop(CART_SESSION_KEY, None)
    guest = _guest_cart(request, guest_id)
    if guest is None:
        return
    if guest.items.exists():
        target, _ = Cart.objects.get_or_create(user=user)
        guest.items.update(cart=target)
        if guest.promo_code and not target.promo_code:
            target.promo_code = guest.promo_code
            target.save(update_fields=["promo_code"])
    guest.delete()


# ── DTOs ──


def price_line(item: CartItem) -> dict:
    product = item.product
    dto = product_dto(product)
    is_rent = item.mode == Mode.RENT
    days = item.rent_days or 1
    if is_rent:
        unit = rental_line_price(product.rent_rate or 0, product.plans.all(), product.add_ons.all(), item.add_on_keys, days)
    else:
        unit = product.buy_price
    qty = 1 if is_rent else item.qty
    return {
        "id": item.pk,
        "product": dto,
        "mode": "rent" if is_rent else "buy",
        "qty": qty,
        "rentStart": item.rent_start.isoformat() if item.rent_start else None,
        "rentEnd": (item.rent_start + timedelta(days=days)).isoformat() if item.rent_start else None,
        "rentDays": days if is_rent else None,
        "addOns": list(item.add_on_keys or []),
        "unitPrice": unit,
        "lineTotal": unit * qty,
        "deposit": product.deposit if is_rent else 0,
        "savedForLater": item.saved_for_later,
    }


def cart_dto(cart: Cart | None) -> dict:
    all_lines = [price_line(i) for i in cart.items.all()] if cart else []
    lines = [l for l in all_lines if not l["savedForLater"]]
    promo = PromoCode.objects.filter(code=cart.promo_code, active=True).first() if cart and cart.promo_code else None
    purchases = sum(l["lineTotal"] for l in lines if l["mode"] == "buy")
    rentals = sum(l["lineTotal"] for l in lines if l["mode"] == "rent")
    deposit = sum(l["deposit"] for l in lines)
    return {
        "id": str(cart.id) if cart else None,
        "lines": lines,
        "saved": [l for l in all_lines if l["savedForLater"]],
        "promo": {"code": promo.code, "percentOff": promo.percent_off} if promo else None,
        "totals": compute_totals(purchases, rentals, deposit, promo.percent_off if promo else 0),
        "count": sum(l["qty"] for l in lines),
    }


def cart_dto_by_id(cart_id) -> dict:
    return cart_dto(cart_queryset().filter(id=cart_id).first())


# ── Mutations ──


def add_to_cart(cart: Cart, data: dict):
    product = Product.objects.prefetch_related("add_ons").filter(slug=data["productId"]).first()
    if not product:
        raise ApiError("Product not found", 404)

    if data["mode"] == "rent":
        if not product.rent_rate:
            raise ApiError("This item can't be rented")
        days = min(90, max(1, data.get("rentDays") or 1))
        start = data.get("rentStart") or (shop_today() + timedelta(days=1))
        if start < shop_today():
            raise ApiError("Choose a start date from today onwards", 422, "rentStart")
        valid = {a.key for a in product.add_ons.all()}
        add_on_keys = [k for k in (data.get("addOns") or []) if k in valid]
        # one rental line per product: booking again replaces the dates
        existing = CartItem.objects.filter(cart=cart, product=product, mode=Mode.RENT).first()
        if existing:
            existing.rent_start, existing.rent_days, existing.add_on_keys, existing.saved_for_later = start, days, add_on_keys, False
            existing.save()
        else:
            CartItem.objects.create(cart=cart, product=product, mode=Mode.RENT, qty=1, rent_start=start, rent_days=days, add_on_keys=add_on_keys)
        return

    if product.rent_only:
        raise ApiError("This item is for rent only")
    if product.stock <= 0 and not product.ships_in_days:
        raise ApiError("Sorry, this item is out of stock")
    qty = min(20, max(1, data.get("qty") or 1))
    existing = CartItem.objects.filter(cart=cart, product=product, mode=Mode.BUY).first()
    if existing:
        existing.qty = min(20, existing.qty + qty)
        existing.saved_for_later = False
        existing.save()
    else:
        CartItem.objects.create(cart=cart, product=product, mode=Mode.BUY, qty=qty)
