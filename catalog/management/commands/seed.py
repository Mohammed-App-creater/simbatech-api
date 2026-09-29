"""
Seeds the catalog shown in the design (12 products, categories, brands, rental plans, add-ons),
the SIMBA10 promo code, a demo customer with orders, and a staff account for the admin site.

    python manage.py seed      (idempotent: re-running updates the catalog and recreates the demo orders)

Demo customer: demo@simbatech.et / simbatech123
Admin:         admin@simbatech.et / admin12345   (or ADMIN_PASSWORD from the environment)
"""

import os
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Address, User, WishlistItem
from cart.models import Mode
from catalog.models import AddOn, Brand, Category, Product, PromoCode, RentalPlan
from core.pricing import compute_totals, rental_base_price, shop_today
from orders.models import Order, OrderEvent, OrderItem, OrderStatus, PaymentMethod, PaymentStatus, RentalStatus, TRACK_STEPS

CATEGORIES = [
    ("Electronics", "Electronics", "headphones", "#E0F1FF"),
    ("Phones", "Electronics", "phone", "#EEE8FF"),
    ("Wearables", "Electronics", "watch", "#FFEADB"),
    ("Home & Living", "Home & Living", "sofa", "#DDF5EA"),
    ("Kitchen", "Kitchen", "espresso", "#F3EEE6"),
    ("Fashion", "Fashion", "sneaker", "#FFEADB"),
    ("Beauty", "Beauty", "skincare", "#FFE4EF"),
    ("Tools & DIY", "Tools & DIY", "drill", "#FFF4C7"),
    ("Events & Party", "Events & Party", "tent", "#D9F3F0"),
    ("Sports", "Sports", "bike", "#DDF5EA"),
    ("Baby & Kids", "Baby & Kids", "blocks", "#E0F1FF"),
]

BRANDS = ["Nova", "Aero", "Pulse", "Lumen", "Casa Verde", "Orbit"]

PRODUCTS = [
    dict(name="Lumen Z6 Camera", cat="Electronics", brand="Lumen", kind="camera", bg="#E0F1FF", buy=139000, rent=2500, deposit=20000, rating=4.8, reviews=212, stock=6, free=True,
         description="A mirrorless camera for photos and 4K video. Rent it for a shoot, a wedding or a weekend away — or buy it to keep, with warranty. Every rental is checked, cleaned and charged before it reaches you.",
         add_ons=[("battery", "Extra battery", 300, "Shoot all day without recharging"), ("lens", "Spare lens", 900, "50mm f/1.8 prime"), ("cover", "Damage cover", 200, "Lowers your excess to ETB 5,000")]),
    dict(name="Pulse ANC Headphones", cat="Electronics", brand="Pulse", kind="headphones", bg="#EEE8FF", buy=18900, was=23500, rating=4.9, reviews=540, stock=6, sold=78, free=True,
         description="Wireless over-ear headphones with active noise cancelling and 30 hours of battery."),
    dict(name="Aero X Pro", cat="Phones", brand="Aero", kind="phone", bg="#DDF5EA", buy=89500, rating=4.7, reviews=318, stock=14, free=True,
         description="A 6.5-inch flagship phone with a triple camera, all-day battery and dual SIM."),
    dict(name="Orbit Watch 2", cat="Wearables", brand="Orbit", kind="watch", bg="#FFEADB", buy=21500, was=26900, rating=4.6, reviews=187, stock=3, sold=90, free=False,
         description="A fitness smartwatch with heart-rate, sleep tracking and a week of battery life."),
    dict(name="Linen 3-Seater Sofa", cat="Home & Living", brand="Casa Verde", kind="sofa", bg="#F3EEE6", buy=84900, rating=4.7, reviews=96, stock=0, ships_in_days=5, free=False,
         description="A deep, comfortable three-seater in washable linen, made to order."),
    dict(name="Barista Espresso Machine", cat="Kitchen", brand="Casa Verde", kind="espresso", bg="#FFF4C7", buy=38500, was=45000, rating=4.6, reviews=143, stock=9, sold=55, free=True,
         description="A 15-bar espresso machine with a steam wand for café-style coffee at home."),
    dict(name="Street Runner Sneakers", cat="Fashion", brand="Aero", kind="sneaker", bg="#FFE4EF", buy=9800, was=12400, rating=4.5, reviews=402, stock=12, sold=40, free=False,
         description="Lightweight everyday runners with a cushioned sole."),
    dict(name="Glow Skincare Duo", cat="Beauty", brand="Lumen", kind="skincare", bg="#D9F3F0", buy=4600, rating=4.8, reviews=265, stock=40, free=False,
         description="A gentle cleanser and hydrating serum for daily use."),
    dict(name="Cordless Drill Kit", cat="Tools & DIY", brand="Nova", kind="drill", bg="#FFF4C7", buy=14500, rent=800, deposit=2000, rating=4.9, reviews=121, stock=10, free=True,
         description="An 18V cordless drill with two batteries, a charger and a case.",
         add_ons=[("bits", "Drill bit set", 100, "Wood, metal and masonry")]),
    dict(name="Canopy Tent 3 × 3 m", cat="Events & Party", brand="Nova", kind="tent", bg="#FFEADB", buy=45000, rent=3500, rent_only=True, deposit=5000, rating=4.7, reviews=88, stock=8, free=True,
         description="A pop-up 3 × 3 m canopy for garden parties and outdoor events.",
         add_ons=[("setup", "Set-up & take-down", 1000, "Our team puts it up and takes it down")]),
    dict(name="Trail Mountain Bike", cat="Sports", brand="Orbit", kind="bike", bg="#DDF5EA", buy=65000, rent=1200, deposit=8000, rating=4.5, reviews=74, stock=0, ships_in_days=3, free=False,
         description="A 21-speed hardtail mountain bike with front suspension.",
         add_ons=[("helmet", "Helmet", 100, "")]),
    dict(name="Stack & Learn Blocks", cat="Baby & Kids", brand="Nova", kind="blocks", bg="#E0F1FF", buy=2900, was=3600, rating=4.8, reviews=156, stock=4, sold=84, free=False,
         description="Soft, stackable learning blocks with letters and numbers."),
]


def product_slug(name: str) -> str:
    # matches the slugs the site links to, e.g. "canopy-tent-3-x-3-m"
    return slugify(name.replace("&", "and").replace("×", "x"))


def round100(n: float) -> int:
    return int(round(n / 100) * 100)


def plans_for(rate: int):
    """Discounts for multi-day rentals (camera: 3 days 6,900 · 1 week 14,000 · 2 weeks 25,000)."""
    return [(1, rate), (3, round100(rate * 3 * 0.92)), (7, round100(rate * 7 * 0.8)), (14, round100(rate * 14 * 0.714))]


class Command(BaseCommand):
    help = "Seed the catalog, promo code, demo customer and admin account"

    @transaction.atomic
    def handle(self, *args, **options):
        for i, (name, department, kind, bg) in enumerate(CATEGORIES):
            Category.objects.update_or_create(slug=slugify(name.replace("&", "and")), defaults=dict(name=name, department=department, kind=kind, bg=bg, sort=i))
        for name in BRANDS:
            Brand.objects.update_or_create(slug=slugify(name), defaults=dict(name=name))

        for p in PRODUCTS:
            product, _ = Product.objects.update_or_create(
                slug=product_slug(p["name"]),
                defaults=dict(
                    name=p["name"],
                    description=p["description"],
                    category=Category.objects.get(name=p["cat"]),
                    brand=Brand.objects.get(name=p["brand"]),
                    kind=p["kind"],
                    bg=p["bg"],
                    buy_price=p["buy"],
                    was_price=p.get("was"),
                    rent_rate=p.get("rent"),
                    rent_only=p.get("rent_only", False),
                    deposit=p.get("deposit", 0),
                    rating=p["rating"],
                    review_count=p["reviews"],
                    stock=p["stock"],
                    sold_percent=p.get("sold", 0),
                    free_delivery=p["free"],
                    ships_in_days=p.get("ships_in_days"),
                ),
            )
            product.plans.all().delete()
            product.add_ons.all().delete()
            if p.get("rent"):
                RentalPlan.objects.bulk_create([RentalPlan(product=product, days=d, price=price) for d, price in plans_for(p["rent"])])
            for key, label, per_day, note in p.get("add_ons", []):
                AddOn.objects.create(product=product, key=key, label=label, per_day=per_day, note=note)

        PromoCode.objects.update_or_create(code="SIMBA10", defaults=dict(percent_off=10, active=True))

        # ── Staff account for /admin ──
        if not User.objects.filter(email="admin@simbatech.et").exists():
            User.objects.create_superuser(email="admin@simbatech.et", password=os.environ.get("ADMIN_PASSWORD", "admin12345"), name="Simbatech Admin")

        # ── Demo customer ──
        demo, created = User.objects.get_or_create(email="demo@simbatech.et", defaults=dict(name="Selam Tesfaye", phone="0911000000"))
        if created:
            demo.set_password("simbatech123")
            demo.save()
        Address.objects.filter(user=demo).delete()
        Address.objects.create(user=demo, label="Home", line1="Bole Road, House 12", area="Bole", city="Addis Ababa", phone="0911000000", is_default=True)
        Address.objects.create(user=demo, label="Work", line1="Churchill Ave, 4th floor", area="Piassa", city="Addis Ababa", phone="0911000000", notes="Reception, 9am–5pm")

        Order.objects.filter(user=demo).delete()
        today = shop_today()
        now = timezone.now()
        address = {"label": "Home", "line1": "Bole Road, House 12", "area": "Bole", "city": "Addis Ababa", "phone": "0911000000", "notes": None}
        by_name = {p.name: p for p in Product.objects.all()}

        demo_orders = [
            dict(n=2, ago=0, status=OrderStatus.OUT_FOR_DELIVERY, pay=PaymentMethod.TELEBIRR, lines=[("Pulse ANC Headphones", "buy"), ("Orbit Watch 2", "buy")]),
            dict(n=3, ago=2, status=OrderStatus.PACKED, pay=PaymentMethod.CARD, lines=[("Barista Espresso Machine", "buy")]),
            dict(n=4, ago=4, status=OrderStatus.DELIVERED, pay=PaymentMethod.TELEBIRR, lines=[("Lumen Z6 Camera", "rent", 7, -3, RentalStatus.ACTIVE)]),
            dict(n=5, ago=1, status=OrderStatus.DELIVERED, pay=PaymentMethod.COD, lines=[("Canopy Tent 3 × 3 m", "rent", 3, 0, RentalStatus.ACTIVE)]),
            dict(n=1, ago=20, status=OrderStatus.DELIVERED, pay=PaymentMethod.TELEBIRR, lines=[("Street Runner Sneakers", "buy"), ("Glow Skincare Duo", "buy")]),
        ]
        for o in demo_orders:
            created_at = now - timedelta(days=o["ago"])
            purchases = rentals = deposits = 0
            items = []
            for line in o["lines"]:
                product = by_name[line[0]]
                if line[1] == "buy":
                    purchases += product.buy_price
                    items.append(dict(product=product, name=product.name, kind=product.kind, bg=product.bg, mode=Mode.BUY, qty=1, unit_price=product.buy_price, line_total=product.buy_price))
                else:
                    _, _, days, start_offset, rstatus = line
                    price = rental_base_price(product.rent_rate, product.plans.all(), days)
                    rentals += price
                    deposits += product.deposit
                    start = today + timedelta(days=start_offset)
                    items.append(dict(product=product, name=product.name, kind=product.kind, bg=product.bg, mode=Mode.RENT, qty=1, unit_price=price, line_total=price,
                                      rent_start=start, rent_end=start + timedelta(days=days), rent_days=days, deposit=product.deposit, rental_status=rstatus))
            totals = compute_totals(purchases, rentals, deposits)
            paid = o["pay"] != PaymentMethod.COD or o["status"] == OrderStatus.DELIVERED
            order = Order.objects.create(
                number=f"ST-{o['n']:06d}", user=demo, contact_name=demo.name, contact_phone="0911000000", contact_email=demo.email, address=address,
                delivery_date=(created_at + timedelta(days=1)).date(), delivery_window="12pm – 3pm", payment_method=o["pay"],
                payment_status=PaymentStatus.PAID if paid else PaymentStatus.PENDING, status=o["status"], purchases_total=purchases, rentals_total=rentals,
                delivery_fee=totals["deliveryFee"], deposit_total=deposits, total=totals["total"],
            )
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            for item in items:
                OrderItem.objects.create(order=order, **item)
            reached = TRACK_STEPS.index(o["status"])
            for i, step in enumerate(TRACK_STEPS[: reached + 1]):
                event = OrderEvent.objects.create(order=order, status=step)
                OrderEvent.objects.filter(pk=event.pk).update(created_at=created_at + timedelta(hours=3 * i))

        WishlistItem.objects.filter(user=demo).delete()
        for name in ["Linen 3-Seater Sofa", "Aero X Pro", "Trail Mountain Bike", "Glow Skincare Duo"]:
            WishlistItem.objects.create(user=demo, product=by_name[name])

        self.stdout.write(self.style.SUCCESS(f"Seeded {Product.objects.count()} products, {Category.objects.count()} categories, {Order.objects.count()} orders."))
