"""
Products are sent to the site in the shape its screens expect (id = slug, cat, dept, brand,
kind, bg, buy, was, rent, rentOnly, ...). Keep these keys stable: the Next.js screens read them.
"""

from django.db.models import Count

from .models import Brand, Bundle, Category, Page, Product, Review, StoreSettings


def product_queryset():
    return Product.objects.select_related("category", "brand").prefetch_related("plans", "add_ons", "variants")


def product_dto(p: Product) -> dict:
    d = {
        "id": p.slug,
        "name": p.name,
        "description": p.description,
        "cat": p.category.name,
        "dept": p.category.department,
        "brand": p.brand.name,
        "kind": p.kind,
        "bg": p.bg,
        "sku": p.sku or None,
        "buy": p.buy_price,
        "rentOnly": p.rent_only,
        "deposit": p.deposit,
        "rating": f"{p.rating:.1f}",
        "reviews": p.review_count,
        "avail": p.stock > 0,
        "left": p.stock,
        "sold": p.sold_percent,
        "free": p.free_delivery,
        "warranty": p.warranty or None,
        "specs": p.specs or [],
        "inTheBox": p.in_the_box or [],
        "plans": [{"days": pl.days, "price": pl.price} for pl in p.plans.all()],
        "addOns": [
            {"key": a.key, "label": a.label, "perDay": a.per_day, **({"note": a.note} if a.note else {})} for a in p.add_ons.all()
        ],
        "variants": [{"key": v.key, "label": v.label, "extra": v.extra_price} for v in p.variants.all()],
    }
    if p.was_price:
        d["was"] = p.was_price
    if p.rent_rate:
        d["rent"] = p.rent_rate
    if p.ships_in_days:
        d["shipsInDays"] = p.ships_in_days
    return d


def category_list() -> list[dict]:
    out = []
    for c in Category.objects.prefetch_related("products"):
        products = list(c.products.all())
        can_rent = any(p.rent_rate for p in products)
        can_buy = any(not p.rent_only for p in products)
        out.append(
            {
                "slug": c.slug,
                "label": c.name,
                "dept": c.department,
                "kind": c.kind,
                "bg": c.bg,
                "count": len(products),
                "tag": "Buy · Rent" if can_buy and can_rent else ("Rent" if can_rent else "Buy"),
            }
        )
    return out


def brand_list() -> list[dict]:
    return [{"slug": b.slug, "name": b.name, "count": b.n} for b in Brand.objects.annotate(n=Count("products"))]


def bundle_list() -> list[dict]:
    out = []
    for b in Bundle.objects.prefetch_related("items__product"):
        items = list(b.items.all())
        products = [i.product for i in items if i.product and i.product.rent_rate]
        out.append(
            {
                "id": b.slug,
                "name": b.name,
                "desc": b.description,
                "bg": b.bg,
                "k1": b.kind1,
                "k2": b.kind2,
                "count": len(items),
                "items": [{"label": i.label, "productId": i.product.slug if i.product else None, "qty": i.qty} for i in items],
                "productIds": [p.slug for p in products],
                "price": sum(p.rent_rate for p in products),  # per day, from the day rates of the products we book
            }
        )
    return out


def review_dto(r: Review) -> dict:
    return {
        "id": r.pk,
        "rating": r.rating,
        "title": r.title,
        "body": r.body,
        "author": r.user.name.split(" ")[0] + (" " + r.user.name.split(" ")[-1][0] + "." if " " in r.user.name else ""),
        "createdAt": r.created_at.isoformat(),
    }


def reviews_payload(product: Product, user=None) -> dict:
    reviews = list(product.reviews.select_related("user"))
    counts = {s: 0 for s in range(1, 6)}
    for r in reviews:
        counts[r.rating] += 1
    n = len(reviews)
    return {
        "rating": f"{product.rating:.1f}",
        "count": n,
        "distribution": [{"stars": s, "count": counts[s], "percent": round(counts[s] * 100 / n) if n else 0} for s in (5, 4, 3, 2, 1)],
        "items": [review_dto(r) for r in reviews],
        "mine": next((review_dto(r) for r in reviews if user and r.user_id == user.pk), None),
    }


def page_dto(p: Page) -> dict:
    return {"slug": p.slug, "title": p.title, "summary": p.summary, "body": p.body, "updatedAt": p.updated_at.isoformat()}


def store_dto() -> dict:
    s = StoreSettings.get()
    return {
        "name": s.store_name,
        "city": s.city,
        "address": s.address,
        "phone": s.phone,
        "whatsapp": s.whatsapp,
        "email": s.support_email,
        "hours": s.hours,
        "sameDayCutoffHour": s.same_day_cutoff_hour,
        "pickupReadyHours": s.pickup_ready_hours,
        "returnDays": s.return_days,
        "depositRefundDays": s.deposit_refund_days,
        "warranty": s.warranty_default,
        "damagePolicy": s.damage_policy,
        "payOnDeliveryTerms": s.pay_on_delivery_terms,
    }
