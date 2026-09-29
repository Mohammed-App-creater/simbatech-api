from django.conf import settings
from django.db import models


class Category(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60, unique=True)
    department = models.CharField(max_length=60)  # top-level department used by filters and the mega menu
    kind = models.CharField(max_length=30)  # product render used as the category's illustration
    bg = models.CharField(max_length=9)
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Brand(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """All prices are whole birr (ETB)."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    kind = models.CharField(max_length=30, help_text="Which illustration the site draws for this product")
    bg = models.CharField(max_length=9, help_text="Card background colour, e.g. #E0F1FF")
    sku = models.CharField(max_length=40, blank=True)
    buy_price = models.PositiveIntegerField()
    was_price = models.PositiveIntegerField(null=True, blank=True, help_text="Set when on sale")
    rent_rate = models.PositiveIntegerField(null=True, blank=True, help_text="Per day; empty = not rentable")
    rent_only = models.BooleanField(default=False)
    deposit = models.PositiveIntegerField(default=0, help_text="Refundable, rentals only")
    rating = models.FloatField(default=0, help_text="Recomputed from reviews")
    review_count = models.PositiveIntegerField(default=0, help_text="Recomputed from reviews")
    stock = models.PositiveIntegerField(default=0, help_text="Units available to buy / rent now")
    sold_percent = models.PositiveSmallIntegerField(default=0, help_text="Flash-deal progress bar")
    free_delivery = models.BooleanField(default=False)
    ships_in_days = models.PositiveSmallIntegerField(null=True, blank=True, help_text="For items that are not in stock")
    warranty = models.CharField(max_length=60, blank=True, help_text='e.g. "12-month"')
    specs = models.JSONField(default=list, blank=True, help_text='[["Sensor", "24 MP full-frame"], ...]')
    in_the_box = models.JSONField(default=list, blank=True, help_text='["Camera body", "Battery", ...]')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.name

    def recompute_rating(self):
        agg = self.reviews.aggregate(avg=models.Avg("rating"), n=models.Count("id"))
        self.rating = round(agg["avg"] or 0, 1)
        self.review_count = agg["n"] or 0
        self.save(update_fields=["rating", "review_count"])


class Variant(models.Model):
    """A choice within a product that changes the purchase price, e.g. "With kit lens" (+ETB 18,000)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    key = models.SlugField()
    label = models.CharField(max_length=60)
    extra_price = models.PositiveIntegerField(default=0)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("product", "key")]
        ordering = ["sort", "id"]

    def __str__(self):
        return f"{self.product.name}: {self.label}"


class RentalPlan(models.Model):
    """A discounted bundle of days, e.g. 3 days for ETB 6,900."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="plans")
    days = models.PositiveSmallIntegerField()
    price = models.PositiveIntegerField()

    class Meta:
        unique_together = [("product", "days")]
        ordering = ["days"]

    def __str__(self):
        return f"{self.product.name}: {self.days} days for {self.price}"


class AddOn(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="add_ons")
    key = models.SlugField()
    label = models.CharField(max_length=60)
    note = models.CharField(max_length=120, blank=True)
    per_day = models.PositiveIntegerField()

    class Meta:
        unique_together = [("product", "key")]
        ordering = ["id"]

    def __str__(self):
        return f"{self.product.name}: {self.label}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # 1–5
    title = models.CharField(max_length=80, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("product", "user")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}★ {self.product.name} by {self.user.name}"


class Bundle(models.Model):
    """A rental set for an occasion. Booking it adds each product in it to the cart as a rental."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=160)
    bg = models.CharField(max_length=9)
    kind1 = models.CharField(max_length=30, help_text="Main illustration")
    kind2 = models.CharField(max_length=30, help_text="Small illustration")
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "id"]

    def __str__(self):
        return self.name


class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="items")
    label = models.CharField(max_length=60)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, help_text="The product booked for this item, if it is one we stock")
    qty = models.PositiveSmallIntegerField(default=1)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "id"]

    def __str__(self):
        return f"{self.bundle.name}: {self.label}"


class PromoCode(models.Model):
    code = models.CharField(max_length=30, primary_key=True)
    percent_off = models.PositiveSmallIntegerField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} ({self.percent_off}% off)"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Page(models.Model):
    """A content page (Help centre, Delivery, Returns, Terms, ...) edited in the admin."""

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=80)
    summary = models.CharField(max_length=200, blank=True)
    body = models.TextField(help_text="HTML")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class ContactMessage(models.Model):
    class Topic(models.TextChoices):
        SUPPORT = "support", "Help with an order"
        SELL = "sell", "Sell or list with us"
        CAREERS = "careers", "Careers"
        OTHER = "other", "Something else"

    topic = models.CharField(max_length=10, choices=Topic.choices, default=Topic.OTHER)
    name = models.CharField(max_length=80)
    contact = models.CharField(max_length=120, help_text="Phone or email")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_topic_display()} from {self.name}"


class StoreSettings(models.Model):
    """The store's own details, shown across the site. One row, edited in the admin."""

    store_name = models.CharField(max_length=60, default="Simbatech")
    city = models.CharField(max_length=60, default="Addis Ababa")
    address = models.CharField(max_length=160, default="Bole Road, near Edna Mall, Addis Ababa")
    phone = models.CharField(max_length=20, default="0911 000 000")
    whatsapp = models.CharField(max_length=20, default="0911 000 000")
    support_email = models.EmailField(default="hello@simbatech.et")
    hours = models.CharField(max_length=60, default="Mon–Sat, 8am–7pm")
    same_day_cutoff_hour = models.PositiveSmallIntegerField(default=16, help_text="Orders before this hour (24h) can be delivered today")
    pickup_ready_hours = models.PositiveSmallIntegerField(default=2)
    return_days = models.PositiveSmallIntegerField(default=7, help_text="Days to return a purchase")
    deposit_refund_days = models.PositiveSmallIntegerField(default=3, help_text="Days to refund a rental deposit after collection")
    warranty_default = models.CharField(max_length=60, default="12-month manufacturer's warranty")
    damage_policy = models.CharField(max_length=200, default="Normal wear is fine. Damage beyond that is charged from the deposit, up to the excess shown on the product.")
    pay_on_delivery_terms = models.CharField(max_length=200, default="Pay the driver by Telebirr or card when your order arrives. Orders over ETB 50,000 need a 20% deposit online.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "store settings"

    def __str__(self):
        return self.store_name

    @classmethod
    def get(cls):
        obj = cls.objects.first()
        return obj or cls.objects.create()
