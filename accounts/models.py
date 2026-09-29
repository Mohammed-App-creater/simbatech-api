from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, name, password=None, email=None, phone=None, **extra):
        if not email and not phone:
            raise ValueError("A user needs an email address or a phone number")
        user = self.model(name=name, email=self.normalize_email(email) or None, phone=phone or None, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()  # Google / OTP accounts until they choose a password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, name="Admin", **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(name=name, password=password, email=email, **extra)


def default_notification_prefs():
    return {"sms": True, "email": True, "remind": True, "deals": False}


class User(AbstractBaseUser, PermissionsMixin):
    """A customer (or staff member). Signs in with a phone number or an email address."""

    name = models.CharField(max_length=80)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    google_sub = models.CharField(max_length=64, unique=True, null=True, blank=True, help_text="Google account id when signed up with Google")
    notification_prefs = models.JSONField(default=default_notification_prefs, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return f"{self.name} ({self.email or self.phone})"


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=30)  # "Home", "Work", ...
    line1 = models.CharField(max_length=120)
    area = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    notes = models.CharField(max_length=200, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "created_at"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.label}: {self.line1}, {self.area}"


class WishlistItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "product")]
        ordering = ["-created_at"]


class SavedPaymentMethod(models.Model):
    """
    A customer's saved way to pay, for pre-filling checkout. Only display details are kept:
    a Telebirr number, or a card's brand, last four digits and expiry. Never a full card number.
    """

    class Kind(models.TextChoices):
        TELEBIRR = "telebirr", "Telebirr"
        CARD = "card", "Card"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment_methods")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    label = models.CharField(max_length=40, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    brand = models.CharField(max_length=20, blank=True)  # Visa, Mastercard
    last4 = models.CharField(max_length=4, blank=True)
    expiry = models.CharField(max_length=5, blank=True)  # MM/YY
    holder = models.CharField(max_length=80, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.phone or ('•••• ' + self.last4)}"


class OtpCode(models.Model):
    """A one-time code sent by SMS, for signing in or resetting a password. Stored hashed."""

    class Purpose(models.TextChoices):
        LOGIN = "login", "Sign in"
        RESET = "reset", "Password reset"

    phone = models.CharField(max_length=20, db_index=True)
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
