from django.contrib import admin

from .models import AddOn, Brand, Category, NewsletterSubscriber, Product, PromoCode, RentalPlan


class RentalPlanInline(admin.TabularInline):
    model = RentalPlan
    extra = 0


class AddOnInline(admin.TabularInline):
    model = AddOn
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "buy_price", "was_price", "rent_rate", "rent_only", "stock", "rating")
    list_filter = ("category", "brand", "rent_only", "free_delivery")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RentalPlanInline, AddOnInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "category", "brand")}),
        ("Appearance", {"fields": ("kind", "bg")}),
        ("Pricing", {"fields": ("buy_price", "was_price", "rent_rate", "rent_only", "deposit")}),
        ("Stock & delivery", {"fields": ("stock", "ships_in_days", "free_delivery", "sold_percent")}),
        ("Reviews", {"fields": ("rating", "review_count")}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "kind", "sort")
    list_editable = ("sort",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "active")
    list_editable = ("active",)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")
    search_fields = ("email",)
