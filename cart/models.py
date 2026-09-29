import uuid

from django.conf import settings
from django.db import models


class Mode(models.TextChoices):
    BUY = "BUY", "Buy"
    RENT = "RENT", "Rent"


class Cart(models.Model):
    """Guests are identified by the cart id kept in their session; signing in merges it into the user's cart."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="cart")
    promo_code = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user}" if self.user_id else f"Guest cart {self.id}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    variant = models.ForeignKey("catalog.Variant", on_delete=models.SET_NULL, null=True, blank=True)
    mode = models.CharField(max_length=4, choices=Mode.choices)
    qty = models.PositiveSmallIntegerField(default=1)
    rent_start = models.DateField(null=True, blank=True)
    rent_days = models.PositiveSmallIntegerField(null=True, blank=True)
    add_on_keys = models.JSONField(default=list, blank=True)
    saved_for_later = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.qty} × {self.product} ({self.mode})"
