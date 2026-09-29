from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, User, WishlistItem


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("name", "email", "phone", "is_staff", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("is_staff", "is_active")
    inlines = [AddressInline]
    fieldsets = (
        (None, {"fields": ("name", "email", "phone", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("name", "email", "phone", "password1", "password2")}),)
    readonly_fields = ()
    filter_horizontal = ("groups",)


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
