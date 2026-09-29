from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, name, password=None, email=None, phone=None, **extra):
        if not email and not phone:
            raise ValueError("A user needs an email address or a phone number")
        user = self.model(name=name, email=self.normalize_email(email) or None, phone=phone or None, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, name="Admin", **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(name=name, password=password, email=email, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """A customer (or staff member). Signs in with a phone number or an email address."""

    name = models.CharField(max_length=80)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
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
