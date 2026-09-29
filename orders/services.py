"""
Placing, reading and extending orders.

Payment is simulated: there is no Telebirr / card gateway account yet. Telebirr and card payments
are recorded as PAID immediately; pay-on-delivery stays PENDING until delivery. Replace
`settle_payment()` with a real gateway call when merchant credentials are available.
"""

import secrets
from datetime import date, timedelta

from django.db import transaction
from django.db.models import F, Prefetch

from accounts.models import Address
from cart.models import CartItem, Mode
from cart.services import cart_dto_by_id
from catalog.models import Product
from core.errors import ApiError
from core.pricing import compute_totals, shop_today

from .models import Fulfilment, Order, OrderEvent, OrderItem, OrderStatus, PaymentMethod, PaymentStatus, RentalStatus, TRACK_STEPS

METHODS = {"telebirr": PaymentMethod.TELEBIRR, "card": PaymentMethod.CARD, "cod": PaymentMethod.COD}


def settle_payment(method: str) -> str:
    return PaymentStatus.PENDING if method == PaymentMethod.COD else PaymentStatus.PAID


def next_order_number() -> str:
    while True:
        number = f"ST-{secrets.randbelow(900000) + 100000}"
        if not Order.objects.filter(number=number).exists():
            return number


def place_order(cart_id, user, data: dict) -> Order:
    cart = cart_dto_by_id(cart_id)
    if not cart["lines"]:
        raise ApiError("Your cart is empty")

    pickup = data["fulfilment"] == "pickup"
    if pickup and any(l["mode"] == "rent" for l in cart["lines"]):
        raise ApiError("Rentals are delivered and collected by us, so please choose delivery for this order")

    today = shop_today()
    delivery_date: date | None = data.get("deliveryDate")
    if delivery_date and delivery_date < today:
        raise ApiError("Choose a delivery date from today onwards", 422, "deliveryDate")
    same_day = delivery_date == today
    totals = compute_totals(
        cart["totals"]["purchases"],
        cart["totals"]["rentals"],
        cart["totals"]["deposit"],
        cart["promo"]["percentOff"] if cart["promo"] else 0,
        pickup=pickup,
        same_day=same_day,
    )
    method = METHODS[data["payment"]["method"]]
    contact = data["contact"]

    with transaction.atomic():
        address = None
        if not pickup:
            if data.get("addressId") and user:
                saved = Address.objects.filter(pk=_int(data["addressId"]), user=user).first()
                if not saved:
                    raise ApiError("Address not found", 404, "addressId")
                address = {"label": saved.label, "line1": saved.line1, "area": saved.area, "city": saved.city, "phone": saved.phone, "notes": saved.notes or None}
            elif data.get("newAddress"):
                a = data["newAddress"]
                phone = a.get("phone") or contact["phone"]
                address = {"label": a.get("label") or "Delivery", "line1": a["line1"], "area": a["area"], "city": a["city"], "phone": phone, "notes": None}
                if user:
                    is_first = not Address.objects.filter(user=user).exists()
                    Address.objects.create(user=user, label=a.get("label") or "Home", line1=a["line1"], area=a["area"], city=a["city"], phone=phone, is_default=is_first)
            else:
                raise ApiError("Choose a delivery address", 422, "addressId")

        # reserve stock for purchases
        for line in (l for l in cart["lines"] if l["mode"] == "buy"):
            product = Product.objects.select_for_update().get(slug=line["product"]["id"])
            if product.stock < line["qty"] and not product.ships_in_days:
                raise ApiError(f"Only {product.stock} {product.name} left")
            if product.stock > 0:
                product.stock = max(0, product.stock - line["qty"])
                product.save(update_fields=["stock"])

        products = {p.slug: p for p in Product.objects.filter(slug__in=[l["product"]["id"] for l in cart["lines"]])}
        order = Order.objects.create(
            number=next_order_number(),
            user=user,
            contact_name=contact["name"],
            contact_phone=contact["phone"],
            contact_email=contact["email"],
            fulfilment=Fulfilment.PICKUP if pickup else Fulfilment.DELIVERY,
            address=address,
            delivery_date=None if pickup else delivery_date,
            delivery_window="" if pickup else (data.get("deliveryWindow") or ""),
            payment_method=method,
            payment_status=settle_payment(method),
            payment_phone=data["payment"].get("phone") or "",
            purchases_total=totals["purchases"],
            rentals_total=totals["rentals"],
            delivery_fee=totals["deliveryFee"] + totals["sameDayFee"],
            discount=totals["discount"],
            deposit_total=totals["deposit"],
            total=totals["total"],
            promo_code=cart["promo"]["code"] if cart["promo"] else "",
        )
        OrderEvent.objects.create(order=order, status=OrderStatus.PLACED)
        for line in cart["lines"]:
            product = products[line["product"]["id"]]
            is_rent = line["mode"] == "rent"
            OrderItem.objects.create(
                order=order,
                product=product,
                name=product.name,
                kind=product.kind,
                bg=product.bg,
                mode=Mode.RENT if is_rent else Mode.BUY,
                qty=line["qty"],
                unit_price=line["unitPrice"],
                line_total=line["lineTotal"],
                rent_start=date.fromisoformat(line["rentStart"]) if line["rentStart"] else None,
                rent_end=date.fromisoformat(line["rentEnd"]) if line["rentEnd"] else None,
                rent_days=line["rentDays"],
                add_ons=[a for a in line["product"]["addOns"] if a["key"] in line["addOns"]] if is_rent else None,
                deposit=line["deposit"],
                rental_status=RentalStatus.SCHEDULED if is_rent else None,
            )
        CartItem.objects.filter(cart_id=cart_id, saved_for_later=False).delete()
        from cart.models import Cart

        Cart.objects.filter(id=cart_id).update(promo_code="")
    return order


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


# ── Reading orders ──


def order_queryset():
    return Order.objects.prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("product").order_by("id")),
        Prefetch("events", queryset=OrderEvent.objects.order_by("created_at", "id")),
    )


def _iso_day(d: date | None) -> str | None:
    # Midnight in the shop's time zone, so the browser formats the same calendar day.
    return f"{d.isoformat()}T00:00:00+03:00" if d else None


def order_dto(o: Order) -> dict:
    return {
        "id": str(o.id),
        "number": o.number,
        "createdAt": o.created_at.isoformat(),
        "status": o.status,
        "step": max(0, TRACK_STEPS.index(o.status)) if o.status in TRACK_STEPS else 0,
        "events": [{"status": e.status, "at": e.created_at.isoformat(), "note": e.note or None} for e in o.events.all()],
        "contact": {"name": o.contact_name, "phone": o.contact_phone, "email": o.contact_email},
        "fulfilment": "pickup" if o.fulfilment == Fulfilment.PICKUP else "delivery",
        "address": o.address,
        "deliveryDate": _iso_day(o.delivery_date),
        "deliveryWindow": o.delivery_window or None,
        "payment": {"method": o.payment_method.lower(), "status": o.payment_status.lower(), "phone": o.payment_phone or None},
        "totals": {
            "purchases": o.purchases_total,
            "rentals": o.rentals_total,
            "deliveryFee": o.delivery_fee,
            "discount": o.discount,
            "deposit": o.deposit_total,
            "total": o.total,
        },
        "promoCode": o.promo_code or None,
        "items": [
            {
                "id": i.pk,
                "productId": i.product_id,
                "productSlug": i.product.slug,
                "rentRate": i.product.rent_rate,
                "name": i.name,
                "kind": i.kind,
                "bg": i.bg,
                "mode": "rent" if i.mode == Mode.RENT else "buy",
                "qty": i.qty,
                "unitPrice": i.unit_price,
                "lineTotal": i.line_total,
                "rentStart": _iso_day(i.rent_start),
                "rentEnd": _iso_day(i.rent_end),
                "rentDays": i.rent_days,
                "deposit": i.deposit,
                "rentalStatus": i.rental_status.lower() if i.rental_status else None,
                "extendedDays": i.extended_days,
                "extraCharge": i.extra_charge,
                "addOns": i.add_ons or [],
            }
            for i in o.items.all()
        ],
    }


def get_order(order_id, user) -> dict | None:
    """An order the current visitor may see: their own, or (for guests) one whose id they hold."""
    try:
        order = order_queryset().filter(id=order_id).first()
    except Exception:  # not a valid uuid
        return None
    if not order or (order.user_id and order.user_id != (user.pk if user else None)):
        return None
    return order_dto(order)


def list_orders(user) -> list[dict]:
    return [order_dto(o) for o in order_queryset().filter(user=user)]


def extend_rental(item_id, user, days: int = 1) -> dict:
    """Extend a rental by `days`, charged at the product's day rate."""
    item = OrderItem.objects.select_related("product", "order").filter(pk=item_id, mode=Mode.RENT, order__user=user).first()
    if not item or not item.rent_end:
        raise ApiError("Rental not found", 404)
    if item.rental_status == RentalStatus.RETURNED:
        raise ApiError("This rental has already been returned")
    charge = (item.product.rent_rate or 0) * days
    with transaction.atomic():
        item.rent_end = item.rent_end + timedelta(days=days)
        item.rent_days = (item.rent_days or 0) + days
        item.extended_days += days
        item.extra_charge += charge
        item.save()
        Order.objects.filter(pk=item.order_id).update(rentals_total=F("rentals_total") + charge, total=F("total") + charge)
    return {"charge": charge}
