import uuid

from django.conf import settings
from django.db import models

from cart.models import Mode


class OrderStatus(models.TextChoices):
    PLACED = "PLACED", "Placed"
    PACKED = "PACKED", "Packed"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for delivery"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


TRACK_STEPS = [OrderStatus.PLACED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]


class PaymentMethod(models.TextChoices):
    TELEBIRR = "TELEBIRR", "Telebirr"
    CARD = "CARD", "Card"
    COD = "COD", "Pay on delivery"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class Fulfilment(models.TextChoices):
    DELIVERY = "DELIVERY", "Delivery"
    PICKUP = "PICKUP", "Pick up in store"


class RentalStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    ACTIVE = "ACTIVE", "Active"
    RETURNED = "RETURNED", "Returned"


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=12, unique=True)  # ST-123456
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    contact_name = models.CharField(max_length=80)
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField()
    fulfilment = models.CharField(max_length=10, choices=Fulfilment.choices, default=Fulfilment.DELIVERY)
    address = models.JSONField(null=True, blank=True, help_text="Snapshot of the delivery address")
    delivery_date = models.DateField(null=True, blank=True)
    delivery_window = models.CharField(max_length=40, blank=True)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PLACED)
    purchases_total = models.PositiveIntegerField()
    rentals_total = models.PositiveIntegerField()
    delivery_fee = models.PositiveIntegerField()
    discount = models.PositiveIntegerField(default=0)
    deposit_total = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(help_text="Amount charged now (excludes the refundable deposit)")
    promo_code = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number


class OrderItem(models.Model):
    """Snapshots the product's name and price, so the order reads the same if the catalog changes later."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="order_items")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=30)
    bg = models.CharField(max_length=9)
    mode = models.CharField(max_length=4, choices=Mode.choices)
    qty = models.PositiveSmallIntegerField()
    unit_price = models.PositiveIntegerField()
    line_total = models.PositiveIntegerField()
    rent_start = models.DateField(null=True, blank=True)
    rent_end = models.DateField(null=True, blank=True)
    rent_days = models.PositiveSmallIntegerField(null=True, blank=True)
    add_ons = models.JSONField(null=True, blank=True)
    deposit = models.PositiveIntegerField(default=0)
    rental_status = models.CharField(max_length=10, choices=RentalStatus.choices, null=True, blank=True)
    extended_days = models.PositiveSmallIntegerField(default=0)
    extra_charge = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.qty} × {self.name}"


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20, choices=OrderStatus.choices)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.order.number}: {self.status}"
