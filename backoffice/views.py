"""
The staff side of the API, used by the site's /admin pages (simbatech-web: src/app/admin).

Every endpoint needs a signed-in user with `is_staff`. Django's own /admin/ keeps working and is
still the place for what these pages don't cover (categories, brands, bundles, content pages,
staff accounts).
"""

from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, Max, ProtectedError, Q, Sum
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.views import user_dto
from catalog.dto import product_queryset, store_dto
from catalog.models import AddOn, Brand, Category, ContactMessage, Product, PromoCode, RentalPlan, Review, StoreSettings, Variant
from core.errors import ApiError
from core.pricing import SHOP_TZ, shop_today
from orders.models import Order, OrderEvent, OrderItem, OrderStatus, PaymentStatus, RentalStatus
from orders.services import order_dto, order_queryset

from .serializers import (
    KINDS,
    MessagePatchSerializer,
    OrderPatchSerializer,
    ProductSerializer,
    PromoPatchSerializer,
    PromoSerializer,
    RentalPatchSerializer,
    ReviewPatchSerializer,
    StoreSettingsSerializer,
)

LIST_LIMIT = 200  # rows a list endpoint returns at most; the pages say so when there are more
OPEN_STATUSES = [OrderStatus.PLACED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY]
LOW_STOCK = 3


class IsStaff(BasePermission):
    message = "This area is for Simbatech staff"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class StaffView(APIView):
    permission_classes = [IsStaff]


def counts() -> dict:
    """The numbers shown as badges in the admin's menu."""
    return {
        "openOrders": Order.objects.filter(status__in=OPEN_STATUSES).count(),
        "pendingReviews": Review.objects.filter(status=Review.Status.PENDING).count(),
        "openMessages": ContactMessage.objects.filter(handled=False).count(),
    }


class MeView(StaffView):
    def get(self, request):
        return Response({"user": user_dto(request.user), "counts": counts()})


# ── Orders ──


def order_row(o: Order) -> dict:
    items = list(o.items.all())
    return {
        "id": str(o.id),
        "number": o.number,
        "createdAt": o.created_at.isoformat(),
        "status": o.status,
        "customer": o.contact_name,
        "phone": o.contact_phone,
        "fulfilment": o.fulfilment.lower(),
        "deliveryDate": o.delivery_date.isoformat() if o.delivery_date else None,
        "deliveryWindow": o.delivery_window or None,
        "itemCount": sum(i.qty for i in items),
        "thumbs": [{"name": i.name, "kind": i.kind, "bg": i.bg} for i in items[:3]],
        "hasRental": any(i.rental_status for i in items),
        "total": o.total,
        "payment": {"method": o.payment_method.lower(), "status": o.payment_status.lower()},
    }


def order_detail(o: Order) -> dict:
    user = o.user
    return {
        **order_dto(o),
        "paymentRef": o.payment_ref or None,
        "customer": {"id": user.pk, "name": user.name, "email": user.email, "phone": user.phone, "orders": user.orders.count()} if user else None,
    }


def _order(pk) -> Order:
    try:
        order = order_queryset().select_related("user").filter(id=pk).first()
    except Exception:  # not a valid uuid
        order = None
    if not order:
        raise ApiError("Order not found", 404)
    return order


class OrderListView(StaffView):
    """GET /api/admin/orders?status=open|PLACED|PACKED|OUT_FOR_DELIVERY|DELIVERED|CANCELLED&q="""

    def get(self, request):
        wanted = request.query_params.get("status") or ""
        q = (request.query_params.get("q") or "").strip()
        qs = order_queryset()
        if q:
            qs = qs.filter(Q(number__icontains=q) | Q(contact_name__icontains=q) | Q(contact_phone__icontains=q) | Q(contact_email__icontains=q))
        by_status = {row["status"]: row["n"] for row in qs.order_by().values("status").annotate(n=Count("id"))}
        if wanted == "open":
            qs = qs.filter(status__in=OPEN_STATUSES)
        elif wanted in OrderStatus.values:
            qs = qs.filter(status=wanted)
        return Response(
            {
                "orders": [order_row(o) for o in qs[:LIST_LIMIT]],
                "total": qs.count(),
                "counts": {"all": sum(by_status.values()), "open": sum(by_status.get(s, 0) for s in OPEN_STATUSES), **{s: by_status.get(s, 0) for s in OrderStatus.values}},
            }
        )


class OrderDetailView(StaffView):
    def get(self, request, pk):
        return Response(order_detail(_order(pk)))

    def patch(self, request, pk):
        """Move the order along ({status, note?}) and/or record its payment ({paymentStatus})."""
        s = OrderPatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        order = _order(pk)
        with transaction.atomic():
            if "status" in data and data["status"] != order.status:
                order.status = data["status"]
                order.save(update_fields=["status"])
                # the customer's tracking timeline is built from these events
                OrderEvent.objects.create(order=order, status=order.status, note=(data.get("note") or "").strip() or "Updated by staff")
            if "paymentStatus" in data and data["paymentStatus"] != order.payment_status:
                order.payment_status = data["paymentStatus"]
                if order.payment_status == PaymentStatus.PAID:
                    order.paid_at = timezone.now()
                elif order.payment_status in (PaymentStatus.PENDING, PaymentStatus.FAILED):
                    order.paid_at = None
                order.save(update_fields=["payment_status", "paid_at"])
        return Response(order_detail(_order(pk)))


class RentalView(StaffView):
    def patch(self, request, pk):
        """Record a rented item as handed over (ACTIVE) or collected back (RETURNED)."""
        s = RentalPatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        item = OrderItem.objects.filter(pk=pk, rental_status__isnull=False).first()
        if not item:
            raise ApiError("Rental not found", 404)
        item.rental_status = s.validated_data["rentalStatus"]
        item.save(update_fields=["rental_status"])
        return Response(order_detail(_order(item.order_id)))


# ── Reviews (approval) ──


def review_row(r: Review) -> dict:
    return {
        "id": r.pk,
        "rating": r.rating,
        "title": r.title,
        "body": r.body,
        "status": r.status,
        "createdAt": r.created_at.isoformat(),
        "author": {"name": r.user.name, "contact": r.user.email or r.user.phone},
        "product": {"slug": r.product.slug, "name": r.product.name, "kind": r.product.kind, "bg": r.product.bg},
    }


def review_counts() -> dict:
    found = {row["status"]: row["n"] for row in Review.objects.order_by().values("status").annotate(n=Count("id"))}
    return {s: found.get(s, 0) for s in Review.Status.values}


class ReviewListView(StaffView):
    """GET /api/admin/reviews?status=pending|approved|rejected|all (default: pending)"""

    def get(self, request):
        wanted = request.query_params.get("status") or Review.Status.PENDING
        qs = Review.objects.select_related("user", "product")
        if wanted in Review.Status.values:
            qs = qs.filter(status=wanted)
        return Response({"reviews": [review_row(r) for r in qs[:LIST_LIMIT]], "total": qs.count(), "counts": review_counts()})


class ReviewDetailView(StaffView):
    def _review(self, pk) -> Review:
        review = Review.objects.select_related("user", "product").filter(pk=pk).first()
        if not review:
            raise ApiError("Review not found", 404)
        return review

    def patch(self, request, pk):
        """Approve or reject a review. Only approved reviews show on the site and count in the rating."""
        s = ReviewPatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        review = self._review(pk)
        review.status = s.validated_data["status"]
        review.save(update_fields=["status"])
        review.product.recompute_rating()
        return Response({"review": review_row(review), "counts": review_counts()})

    def delete(self, request, pk):
        review = self._review(pk)
        product = review.product
        review.delete()
        product.recompute_rating()
        return Response({"ok": True, "counts": review_counts()})


# ── Products ──


def product_row(p: Product) -> dict:
    return {
        "slug": p.slug,
        "name": p.name,
        "description": p.description,
        "category": p.category.slug,
        "categoryName": p.category.name,
        "brand": p.brand.slug,
        "brandName": p.brand.name,
        "kind": p.kind,
        "bg": p.bg,
        "sku": p.sku,
        "buyPrice": p.buy_price,
        "wasPrice": p.was_price,
        "rentRate": p.rent_rate,
        "rentOnly": p.rent_only,
        "deposit": p.deposit,
        "stock": p.stock,
        "soldPercent": p.sold_percent,
        "freeDelivery": p.free_delivery,
        "shipsInDays": p.ships_in_days,
        "warranty": p.warranty,
        "specs": p.specs or [],
        "inTheBox": p.in_the_box or [],
        "plans": [{"days": pl.days, "price": pl.price} for pl in p.plans.all()],
        "addOns": [{"key": a.key, "label": a.label, "note": a.note, "perDay": a.per_day} for a in p.add_ons.all()],
        "variants": [{"key": v.key, "label": v.label, "extra": v.extra_price} for v in p.variants.all()],
        "rating": f"{p.rating:.1f}",
        "reviews": p.review_count,
        "createdAt": p.created_at.isoformat(),
    }


def product_options() -> dict:
    return {
        "categories": [{"slug": c.slug, "name": c.name, "dept": c.department} for c in Category.objects.all()],
        "brands": [{"slug": b.slug, "name": b.name} for b in Brand.objects.all()],
        "kinds": KINDS,
    }


def _new_slug(name: str) -> str:
    # same rule as the seeded catalog, e.g. "canopy-tent-3-x-3-m"
    base = slugify(name.replace("&", "and").replace("×", "x")) or "product"
    slug, n = base[:50], 2
    while Product.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 50 - len(suffix)] + suffix, n + 1
    return slug


PRODUCT_FIELDS = {
    "name": "name",
    "description": "description",
    "kind": "kind",
    "bg": "bg",
    "sku": "sku",
    "buyPrice": "buy_price",
    "wasPrice": "was_price",
    "rentRate": "rent_rate",
    "rentOnly": "rent_only",
    "deposit": "deposit",
    "stock": "stock",
    "soldPercent": "sold_percent",
    "freeDelivery": "free_delivery",
    "shipsInDays": "ships_in_days",
    "warranty": "warranty",
    "specs": "specs",
    "inTheBox": "in_the_box",
}


def _keyed(rows: list[dict], field: str) -> list[dict]:
    """Give each add-on / variant a key (from its label when none was sent) and insist they differ."""
    seen, out = set(), []
    for row in rows:
        key = row.get("key") or slugify(row["label"])
        if not key or key in seen:
            raise ApiError("Give each one a different name", 422, field)
        seen.add(key)
        out.append({**row, "key": key})
    return out


def save_product(product: Product | None, data: dict) -> Product:
    creating = product is None
    product = product or Product()
    if "category" in data:
        product.category = Category.objects.filter(slug=data["category"]).first()
        if not product.category:
            raise ApiError("Choose a category", 422, "category")
    if "brand" in data:
        product.brand = Brand.objects.filter(slug=data["brand"]).first()
        if not product.brand:
            raise ApiError("Choose a brand", 422, "brand")
    for key, attr in PRODUCT_FIELDS.items():
        if key in data:
            setattr(product, attr, data[key])
    product.was_price = product.was_price or None  # 0 means "not on sale" / "not rentable"
    product.rent_rate = product.rent_rate or None
    if product.was_price and product.was_price <= product.buy_price:
        raise ApiError("The old price must be higher than the current price", 422, "wasPrice")
    if product.rent_only and not product.rent_rate:
        raise ApiError("A rent-only product needs a price per day", 422, "rentRate")

    plans = data.get("plans")
    if plans is not None and len({p["days"] for p in plans}) != len(plans):
        raise ApiError("Each rental plan needs a different number of days", 422, "plans")
    add_ons = _keyed(data["addOns"], "addOns") if "addOns" in data else None
    variants = _keyed(data["variants"], "variants") if "variants" in data else None

    with transaction.atomic():
        if creating:
            product.slug = _new_slug(product.name)
        product.save()
        # rows are matched by days / key, so carts holding a variant or add-on keep pointing at it
        if plans is not None:
            product.plans.exclude(days__in=[p["days"] for p in plans]).delete()
            for p in plans:
                RentalPlan.objects.update_or_create(product=product, days=p["days"], defaults={"price": p["price"]})
        if add_ons is not None:
            product.add_ons.exclude(key__in=[a["key"] for a in add_ons]).delete()
            for a in add_ons:
                AddOn.objects.update_or_create(product=product, key=a["key"], defaults={"label": a["label"], "note": a.get("note", ""), "per_day": a["perDay"]})
        if variants is not None:
            product.variants.exclude(key__in=[v["key"] for v in variants]).delete()
            for i, v in enumerate(variants):
                Variant.objects.update_or_create(product=product, key=v["key"], defaults={"label": v["label"], "extra_price": v.get("extra", 0), "sort": i})
    return product_queryset().get(pk=product.pk)


class ProductListView(StaffView):
    def get(self, request):
        return Response({"products": [product_row(p) for p in product_queryset().order_by("name")], "options": product_options()})

    def post(self, request):
        s = ProductSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(product_row(save_product(None, s.validated_data)), status=status.HTTP_201_CREATED)


class ProductDetailView(StaffView):
    def _product(self, slug) -> Product:
        product = product_queryset().filter(slug=slug).first()
        if not product:
            raise ApiError("Product not found", 404)
        return product

    def get(self, request, slug):
        return Response({"product": product_row(self._product(slug)), "options": product_options()})

    def patch(self, request, slug):
        s = ProductSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        return Response(product_row(save_product(self._product(slug), s.validated_data)))

    def delete(self, request, slug):
        try:
            self._product(slug).delete()
        except ProtectedError:
            raise ApiError("This product is on past orders, so it can't be deleted. Set its stock to 0 to stop selling it.", 409)
        return Response({"ok": True})


# ── Messages from the contact form ──


def message_row(m: ContactMessage) -> dict:
    return {
        "id": m.pk,
        "topic": m.topic,
        "topicLabel": m.get_topic_display(),
        "name": m.name,
        "contact": m.contact,
        "message": m.message,
        "createdAt": m.created_at.isoformat(),
        "handled": m.handled,
    }


def message_counts() -> dict:
    handled = ContactMessage.objects.filter(handled=True).count()
    return {"open": ContactMessage.objects.count() - handled, "handled": handled}


class MessageListView(StaffView):
    """GET /api/admin/messages?show=open|handled|all (default: open)"""

    def get(self, request):
        show = request.query_params.get("show") or "open"
        qs = ContactMessage.objects.all()
        if show in ("open", "handled"):
            qs = qs.filter(handled=show == "handled")
        return Response({"messages": [message_row(m) for m in qs[:LIST_LIMIT]], "total": qs.count(), "counts": message_counts()})


class MessageDetailView(StaffView):
    def _message(self, pk) -> ContactMessage:
        message = ContactMessage.objects.filter(pk=pk).first()
        if not message:
            raise ApiError("Message not found", 404)
        return message

    def patch(self, request, pk):
        s = MessagePatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        message = self._message(pk)
        message.handled = s.validated_data["handled"]
        message.save(update_fields=["handled"])
        return Response({"message": message_row(message), "counts": message_counts()})

    def delete(self, request, pk):
        self._message(pk).delete()
        return Response({"ok": True, "counts": message_counts()})


# ── Customers ──


class CustomerListView(StaffView):
    """GET /api/admin/customers?q= — accounts with what they've ordered (cancelled orders left out)."""

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        counted = ~Q(orders__status=OrderStatus.CANCELLED)
        qs = User.objects.annotate(
            order_count=Count("orders", filter=counted),
            spent=Sum("orders__total", filter=counted),
            last_order=Max("orders__created_at"),
        ).order_by("-created_at")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        return Response(
            {
                "customers": [
                    {
                        "id": u.pk,
                        "name": u.name,
                        "email": u.email,
                        "phone": u.phone,
                        "createdAt": u.created_at.isoformat(),
                        "isStaff": u.is_staff,
                        "isActive": u.is_active,
                        "orders": u.order_count,
                        "spent": u.spent or 0,
                        "lastOrderAt": u.last_order.isoformat() if u.last_order else None,
                    }
                    for u in qs[:LIST_LIMIT]
                ],
                "total": qs.count(),
            }
        )


# ── Promo codes ──


def promo_list() -> list[dict]:
    return [{"code": p.code, "percentOff": p.percent_off, "active": p.active} for p in PromoCode.objects.order_by("code")]


class PromoListView(StaffView):
    def get(self, request):
        return Response({"promos": promo_list()})

    def post(self, request):
        s = PromoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        code = s.validated_data["code"].upper()
        if PromoCode.objects.filter(code__iexact=code).exists():
            raise ApiError("That code already exists", 409, "code")
        PromoCode.objects.create(code=code, percent_off=s.validated_data["percentOff"], active=s.validated_data["active"])
        return Response({"promos": promo_list()}, status=status.HTTP_201_CREATED)


class PromoDetailView(StaffView):
    def _promo(self, code) -> PromoCode:
        promo = PromoCode.objects.filter(code=code).first()
        if not promo:
            raise ApiError("Promo code not found", 404)
        return promo

    def patch(self, request, code):
        s = PromoPatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        promo = self._promo(code)
        if "percentOff" in s.validated_data:
            promo.percent_off = s.validated_data["percentOff"]
        if "active" in s.validated_data:
            promo.active = s.validated_data["active"]
        promo.save()
        return Response({"promos": promo_list()})

    def delete(self, request, code):
        self._promo(code).delete()
        return Response({"promos": promo_list()})


# ── Store details ──

SETTINGS_FIELDS = {
    "name": "store_name",
    "city": "city",
    "address": "address",
    "phone": "phone",
    "whatsapp": "whatsapp",
    "email": "support_email",
    "hours": "hours",
    "sameDayCutoffHour": "same_day_cutoff_hour",
    "pickupReadyHours": "pickup_ready_hours",
    "returnDays": "return_days",
    "depositRefundDays": "deposit_refund_days",
    "warranty": "warranty_default",
    "damagePolicy": "damage_policy",
    "payOnDeliveryTerms": "pay_on_delivery_terms",
}


class SettingsView(StaffView):
    def get(self, request):
        return Response(store_dto())

    def patch(self, request):
        s = StoreSettingsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        store = StoreSettings.get()
        for key, value in s.validated_data.items():
            setattr(store, SETTINGS_FIELDS[key], value)
        store.save()
        return Response(store_dto())


# ── Overview ──


class OverviewView(StaffView):
    """What needs attention today, for the admin's first page."""

    def get(self, request):
        today = shop_today()
        day_start = datetime.combine(today, time.min, tzinfo=SHOP_TZ)
        live = Order.objects.exclude(status=OrderStatus.CANCELLED)
        todays = live.filter(created_at__gte=day_start)
        week = live.filter(created_at__gte=day_start - timedelta(days=6))
        active = OrderItem.objects.filter(rental_status=RentalStatus.ACTIVE)
        by_status = {row["status"]: row["n"] for row in Order.objects.order_by().values("status").annotate(n=Count("id"))}
        low = Product.objects.filter(stock__lte=LOW_STOCK).order_by("stock", "name")
        return Response(
            {
                "user": user_dto(request.user),
                "counts": counts(),
                "ordersToday": todays.count(),
                "salesToday": todays.aggregate(s=Sum("total"))["s"] or 0,
                "ordersWeek": week.count(),
                "salesWeek": week.aggregate(s=Sum("total"))["s"] or 0,
                "toPack": by_status.get(OrderStatus.PLACED, 0),
                "toSend": by_status.get(OrderStatus.PACKED, 0),
                "onTheWay": by_status.get(OrderStatus.OUT_FOR_DELIVERY, 0),
                "activeRentals": active.count(),
                "rentalsDue": active.filter(rent_end__lte=today).count(),  # due back today or overdue
                "lowStock": [{"slug": p.slug, "name": p.name, "kind": p.kind, "bg": p.bg, "stock": p.stock} for p in low[:6]],
                "lowStockCount": low.count(),
                "recentOrders": [order_row(o) for o in order_queryset()[:6]],
                "pendingReviews": [review_row(r) for r in Review.objects.select_related("user", "product").filter(status=Review.Status.PENDING)[:3]],
                "customers": User.objects.filter(is_staff=False).count(),
            }
        )
