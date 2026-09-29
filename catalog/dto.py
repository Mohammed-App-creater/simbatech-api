"""
Products are sent to the site in the shape its screens expect (id = slug, cat, dept, brand,
kind, bg, buy, was, rent, rentOnly, ...). Keep these keys stable: the Next.js screens read them.
"""

from django.db.models import Count

from .models import Brand, Category, Product


def product_queryset():
    return Product.objects.select_related("category", "brand").prefetch_related("plans", "add_ons")


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
        "buy": p.buy_price,
        "rentOnly": p.rent_only,
        "deposit": p.deposit,
        "rating": f"{p.rating:.1f}",
        "reviews": p.review_count,
        "avail": p.stock > 0,
        "left": p.stock,
        "sold": p.sold_percent,
        "free": p.free_delivery,
        "plans": [{"days": pl.days, "price": pl.price} for pl in p.plans.all()],
        "addOns": [
            {"key": a.key, "label": a.label, "perDay": a.per_day, **({"note": a.note} if a.note else {})} for a in p.add_ons.all()
        ],
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
