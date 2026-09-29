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
    buy_price = models.PositiveIntegerField()
    was_price = models.PositiveIntegerField(null=True, blank=True, help_text="Set when on sale")
    rent_rate = models.PositiveIntegerField(null=True, blank=True, help_text="Per day; empty = not rentable")
    rent_only = models.BooleanField(default=False)
    deposit = models.PositiveIntegerField(default=0, help_text="Refundable, rentals only")
    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    stock = models.PositiveIntegerField(default=0, help_text="Units available to buy / rent now")
    sold_percent = models.PositiveSmallIntegerField(default=0, help_text="Flash-deal progress bar")
    free_delivery = models.BooleanField(default=False)
    ships_in_days = models.PositiveSmallIntegerField(null=True, blank=True, help_text="For items that are not in stock")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.name


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
