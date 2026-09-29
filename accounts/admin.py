from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, OtpCode, SavedPaymentMethod, User, WishlistItem


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


class PaymentMethodInline(admin.TabularInline):
    model = SavedPaymentMethod
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("name", "email", "phone", "is_staff", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("is_staff", "is_active")
    inlines = [AddressInline, PaymentMethodInline]
    fieldsets = (
        (None, {"fields": ("name", "email", "phone", "password", "google_sub")}),
        ("Notifications", {"fields": ("notification_prefs",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("name", "email", "phone", "password1", "password2")}),)
    readonly_fields = ("google_sub",)
    filter_horizontal = ("groups",)


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    list_display = ("phone", "purpose", "created_at", "expires_at", "attempts", "used")
    list_filter = ("purpose", "used")
    readonly_fields = ("code_hash",)
