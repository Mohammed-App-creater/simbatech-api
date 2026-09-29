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
from catalog.models import AddOn, Brand, Bundle, BundleItem, Category, Page, Product, PromoCode, RentalPlan, Review, StoreSettings, Variant
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


DETAILS = {
    "Lumen Z6 Camera": dict(sku="LM-Z6", specs=[["Sensor", "24 MP full-frame CMOS"], ["Video", "4K 30fps, Full HD 120fps"], ["Autofocus", "273-point hybrid, eye detection"], ["Screen", "3.2-inch tilting touchscreen"], ["Battery", "Approx. 380 shots"], ["Weight", "675 g with battery"]], box=["Lumen Z6 camera body", "Rechargeable battery", "Charger and cable", "Shoulder strap", "Body cap"]),
    "Pulse ANC Headphones": dict(sku="PL-ANC1", specs=[["Type", "Over-ear, closed back"], ["Noise cancelling", "Active, adaptive"], ["Battery", "30 hours (ANC on)"], ["Connectivity", "Bluetooth 5.3, 3.5 mm"], ["Weight", "254 g"]], box=["Headphones", "USB-C charging cable", "3.5 mm audio cable", "Carry case"]),
    "Aero X Pro": dict(sku="AE-XP", specs=[["Display", "6.5-inch AMOLED, 120 Hz"], ["Cameras", "50 + 12 + 8 MP rear, 32 MP front"], ["Storage", "256 GB"], ["Battery", "5,000 mAh, 65 W charging"], ["SIM", "Dual SIM"]], box=["Aero X Pro", "65 W charger", "USB-C cable", "Clear case"]),
    "Orbit Watch 2": dict(sku="OR-W2", specs=[["Display", "1.4-inch AMOLED"], ["Sensors", "Heart rate, SpO2, GPS"], ["Battery", "Up to 7 days"], ["Water resistance", "5 ATM"]], box=["Orbit Watch 2", "Magnetic charger", "Extra strap"]),
    "Linen 3-Seater Sofa": dict(sku="CV-SOFA3", specs=[["Seats", "3"], ["Fabric", "Washable linen blend"], ["Frame", "Solid wood"], ["Size", "210 x 92 x 85 cm"]], box=["Sofa (delivered assembled)", "Two cushions", "Care guide"]),
    "Barista Espresso Machine": dict(sku="CV-ESP15", specs=[["Pressure", "15 bar"], ["Water tank", "1.5 L"], ["Steam wand", "Yes"], ["Power", "1,350 W"]], box=["Espresso machine", "Portafilter with two baskets", "Tamper", "Milk jug"]),
    "Street Runner Sneakers": dict(sku="AE-SR", specs=[["Upper", "Breathable mesh"], ["Sole", "Cushioned EVA"], ["Sizes", "38-46"]], box=["Pair of sneakers", "Spare laces"]),
    "Glow Skincare Duo": dict(sku="LM-GLOW", specs=[["Cleanser", "150 ml, fragrance-free"], ["Serum", "30 ml, hyaluronic acid"], ["Skin type", "All"]], box=["Gentle cleanser", "Hydrating serum"]),
    "Cordless Drill Kit": dict(sku="NV-DR18", specs=[["Voltage", "18 V"], ["Chuck", "13 mm keyless"], ["Torque settings", "20 + drill"], ["Batteries", "2 x 2.0 Ah"]], box=["Cordless drill", "Two batteries", "Charger", "Carry case"]),
    "Canopy Tent 3 \u00d7 3 m": dict(sku="NV-TENT33", specs=[["Size", "3 x 3 m, 2.6 m high"], ["Frame", "Steel, pop-up"], ["Canopy", "Waterproof polyester"], ["Weight", "22 kg"]], box=["Canopy tent", "Carry bag", "Weight bags", "Ground pegs"]),
    "Trail Mountain Bike": dict(sku="OR-TRAIL", specs=[["Frame", "Aluminium hardtail"], ["Gears", "21-speed"], ["Wheels", "27.5 inch"], ["Suspension", "Front, 100 mm"]], box=["Mountain bike", "Pedals", "Pump"]),
    "Stack & Learn Blocks": dict(sku="NV-BLOCKS", specs=[["Pieces", "24"], ["Material", "Soft foam, washable"], ["Age", "1-4 years"]], box=["24 blocks", "Storage bag"]),
}

REVIEWERS = [("Hana Bekele", "hana@example.com"), ("Dawit Alemu", "dawit@example.com"), ("Meron Tadesse", "meron@example.com"), ("Yonas Haile", "yonas@example.com"), ("Liya Girma", "liya@example.com"), ("Samuel Kebede", "samuel@example.com")]

REVIEWS = {
    "Lumen Z6 Camera": [(5, "Perfect for our wedding", "Rented it for three days. Arrived charged with a clean lens, and the photos are gorgeous."), (5, "Buy it if you shoot often", "Autofocus is fast and the 4K video is very clean."), (4, "Great camera, heavy kit", "Superb image quality. With the kit lens it gets heavy on long days.")],
    "Pulse ANC Headphones": [(5, "Silence on the bus", "The noise cancelling makes the Bole commute quiet. Battery lasts all week."), (5, "Comfortable for hours", "Soft ear cups, no pressure. Sound is warm and clear."), (4, "Good value", "Great sound. The case could be sturdier.")],
    "Aero X Pro": [(5, "Fast and the camera is great", "Photos at night are surprisingly good."), (4, "Solid phone", "Battery easily lasts a day. Wish it came with a screen protector."), (5, "Best phone I have owned", "Smooth screen, quick charging.")],
    "Orbit Watch 2": [(5, "Battery lasts a week", "Exactly as promised, and the sleep tracking is useful."), (4, "Good, strap could be better", "Tracks runs well. The strap is a bit stiff.")],
    "Linen 3-Seater Sofa": [(5, "Beautiful and comfortable", "Deep seats, lovely fabric. Delivered assembled and placed where we wanted."), (4, "Worth the wait", "Took five days to arrive, but the quality is excellent.")],
    "Barista Espresso Machine": [(5, "Cafe coffee at home", "The steam wand makes proper microfoam."), (4, "Good machine", "Takes a few tries to dial in, then great espresso."), (4, "Compact", "Fits under the cupboards. Tank is a little small.")],
    "Street Runner Sneakers": [(5, "Light and comfy", "Wore them all day at work, no sore feet."), (4, "True to size", "Comfortable. The white gets dirty quickly."), (4, "Nice everyday shoe", "Good grip and cushioning.")],
    "Glow Skincare Duo": [(5, "My skin loves it", "Gentle cleanser, no dryness. Serum absorbs fast."), (5, "Repurchased twice", "Simple routine that works."), (4, "Good pair", "Would love a bigger serum bottle.")],
    "Cordless Drill Kit": [(5, "Rented for the shelves", "Two batteries meant no waiting. Came with bits and a case."), (5, "Powerful", "Drilled into concrete with the right bits."), (5, "Great rental", "Clean, charged, and collected on time.")],
    "Canopy Tent 3 \u00d7 3 m": [(5, "Saved our garden party", "Set up in ten minutes; the team even collected it the next morning."), (4, "Sturdy", "Held up in wind with the weight bags."), (5, "Easy booking", "Delivered exactly in the slot we picked.")],
    "Trail Mountain Bike": [(5, "Fun on Entoto trails", "Suspension soaks up the rocks. Brakes are sharp."), (4, "Good bike", "Heavy-ish but solid.")],
    "Stack & Learn Blocks": [(5, "Toddler approved", "Soft, safe, and the letters are clear."), (5, "Washable!", "Survived juice and a bath."), (4, "Good set", "Wish there were more pieces.")],
}

BUNDLES = [
    dict(name="Garden party", description="Shade, seating and sound for up to 30 guests.", bg="#E4F2E6", kind1="tent", kind2="headphones", items=[("Canopy tent", "Canopy Tent 3 \u00d7 3 m"), ("20 chairs", None), ("Speaker", None), ("String lights", None)]),
    dict(name="Photoshoot kit", description="Everything for a pro shoot, ready to go.", bg="#EAF3FA", kind1="camera", kind2="phone", items=[("Lumen Z6", "Lumen Z6 Camera"), ("2 lenses", None), ("Light kit", None), ("Tripod", None)]),
    dict(name="Weekend DIY", description="Tackle the shelves, the fence and the gutters.", bg="#FFF4C7", kind1="drill", kind2="bike", items=[("Cordless drill", "Cordless Drill Kit"), ("Ladder", None), ("Tool set", None), ("Safety kit", None)]),
    dict(name="Kids' birthday", description="Play, shade and seating for a day of fun.", bg="#FFE4EF", kind1="blocks", kind2="tent", items=[("Kids' tent", "Canopy Tent 3 \u00d7 3 m"), ("Tables & chairs", None), ("Toy set", None), ("Party lights", None)]),
]

PAGES = [
    ("help", "Help centre", "Answers to the questions we hear most.", """<h2>Ordering</h2><p>Add items to your cart to buy them, or choose dates to rent them by the day. You can mix purchases and rentals in one order. Pay by Telebirr, CBE Birr, card, or on delivery.</p><h2>Delivery</h2><p>We deliver across the city in the time slot you pick at checkout. Order before the cut-off time for same-day delivery. Rentals are delivered and collected by our team.</p><h2>Rentals</h2><p>Every rental is inspected, cleaned and charged before it reaches you. A refundable deposit is held and returned after collection. You can extend a rental from your account.</p><h2>Still stuck?</h2><p>Use the <a href="/p/contact">contact page</a> and we'll get back to you the same day.</p>"""),
    ("delivery", "Delivery", "Where, when and how much.", """<h2>Areas</h2><p>We deliver across Addis Ababa. Delivery to other cities is available for purchases on request.</p><h2>Times</h2><p>Choose a delivery window at checkout: 9am-12pm, 12pm-3pm, 3pm-6pm or 6pm-8pm. Orders placed before the same-day cut-off can be delivered today.</p><h2>Cost</h2><p>Purchases over ETB 100,000 ship free; otherwise delivery is ETB 500. Same-day delivery adds ETB 450. Rental delivery and collection are always free.</p><h2>Pick up</h2><p>Purchases can be collected from our store instead; we text you when the order is ready.</p>"""),
    ("returns", "Returns", "Changed your mind? No problem.", """<p>Return a purchase within 7 days of delivery, unused and in its original packaging, for a full refund to your payment method. Contact us and we'll arrange collection.</p><p>Faulty items are covered by the manufacturer's warranty shown on the product page; we'll handle the claim for you.</p><p>Rentals aren't returns: our team collects them on the return date.</p>"""),
    ("rental-terms", "Rental terms", "The short version of how renting works.", """<h2>Booking</h2><p>Pick a start date and how long you need the item. Multi-day plans are cheaper per day. You can extend from your account, charged at the daily rate.</p><h2>Deposit</h2><p>A refundable deposit is held for each rental and returned within 3 working days of collection, after a quick inspection.</p><h2>Care and damage</h2><p>Normal wear is fine. Damage beyond that is charged from the deposit, up to the excess shown on the product page. Optional damage cover lowers that excess.</p><h2>Delivery and collection</h2><p>We deliver at the start of your rental and collect it on the return date, both free.</p>"""),
    ("privacy", "Privacy policy", "What we keep and why.", """<p>We store the details you give us to deliver your orders: name, phone, email, delivery address, and your order history. We never store full card numbers; online payments are handled by our payment provider.</p><p>We send order updates by SMS and email, and offers only if you opt in. You can change this in your account settings or unsubscribe at any time.</p><p>To see or delete the data we hold about you, contact us.</p>"""),
    ("terms", "Terms of use", "The rules for using Simbatech.", """<p>By placing an order you agree to these terms. Prices are in Ethiopian birr and include VAT where applicable. We may cancel an order if an item is unavailable and will refund you in full.</p><p>Rentals are subject to our <a href="/p/rental-terms">rental terms</a>. Purchases are subject to our <a href="/p/returns">returns policy</a>.</p>"""),
    ("cookies", "Cookies", "Only what the site needs.", """<p>We use a session cookie to keep you signed in and to remember your cart, and a security cookie to protect forms. We don't use advertising cookies.</p>"""),
    ("about", "About Simbatech", "Everything you need, to own or to rent.", """<p>Simbatech is an Addis Ababa store for electronics, home, fashion, tools and event gear. Buy to keep, or rent by the day for the moments you don't need to own something: a camera for a wedding, a tent for a garden party, a drill for one weekend.</p><p>Every product is genuine and comes with its warranty. Every rental is checked, cleaned and charged before it reaches your door.</p>"""),
    ("careers", "Careers", "Come and build the store with us.", """<p>We're a small team of drivers, technicians, and customer-care staff, and we're growing. If you'd like to work with us, send us a message on the <a href="/p/contact?topic=careers">contact page</a> with a few lines about yourself and what you'd like to do.</p>"""),
    ("sell-with-us", "Sell or list with us", "Turn your gear into income.", """<p>Own equipment that sits idle most of the year? List it for rent on Simbatech. We handle bookings, delivery, collection, cleaning and deposits; you earn a share of every rental.</p><p>Brands and shops can also sell through Simbatech. Tell us what you'd like to list using the <a href="/p/contact?topic=sell">contact page</a> and we'll be in touch within two working days.</p>"""),
    ("contact", "Contact us", "We reply the same day.", """<p>Send us a message using the form below, or call us during opening hours.</p>"""),
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

        for p in PRODUCTS:
            product = Product.objects.get(slug=product_slug(p["name"]))
            details = DETAILS.get(p["name"], {})
            product.sku = details.get("sku", "")
            product.warranty = "12-month" if product.category.department in ("Electronics", "Kitchen", "Tools & DIY", "Sports") else "6-month"
            product.specs = details.get("specs", [])
            product.in_the_box = details.get("box", [])
            product.save(update_fields=["sku", "warranty", "specs", "in_the_box"])

        camera = Product.objects.get(slug=product_slug("Lumen Z6 Camera"))
        Variant.objects.update_or_create(product=camera, key="body", defaults=dict(label="Body only", extra_price=0, sort=0))
        Variant.objects.update_or_create(product=camera, key="kit", defaults=dict(label="With kit lens", extra_price=18000, sort=1))

        for i, b in enumerate(BUNDLES):
            bundle, _ = Bundle.objects.update_or_create(slug=slugify(b["name"].replace("'", "")), defaults=dict(name=b["name"], description=b["description"], bg=b["bg"], kind1=b["kind1"], kind2=b["kind2"], sort=i))
            bundle.items.all().delete()
            for j, (label, product_name) in enumerate(b["items"]):
                BundleItem.objects.create(bundle=bundle, label=label, product=Product.objects.get(slug=product_slug(product_name)) if product_name else None, sort=j)

        for slug, title, summary, body in PAGES:
            Page.objects.update_or_create(slug=slug, defaults=dict(title=title, summary=summary, body=body))
        StoreSettings.get()

        PromoCode.objects.update_or_create(code="SIMBA10", defaults=dict(percent_off=10, active=True))

        # Reviews from a few seed customers (ratings and counts are recomputed from these)
        reviewers = []
        for name, email in REVIEWERS:
            user, created = User.objects.get_or_create(email=email, defaults=dict(name=name))
            if created:
                user.set_unusable_password()
                user.save()
            reviewers.append(user)
        for name, reviews in REVIEWS.items():
            product = Product.objects.get(slug=product_slug(name))
            for k, (rating, title, body) in enumerate(reviews):
                Review.objects.update_or_create(product=product, user=reviewers[(k + len(name)) % len(reviewers)], defaults=dict(rating=rating, title=title, body=body))
            product.recompute_rating()

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

        self.stdout.write(self.style.SUCCESS(f"Seeded {Product.objects.count()} products, {Category.objects.count()} categories, {Bundle.objects.count()} bundles, {Review.objects.count()} reviews, {Page.objects.count()} pages, {Order.objects.count()} orders."))
