from django.contrib import admin

from .models import AddOn, Brand, Bundle, BundleItem, Category, ContactMessage, NewsletterSubscriber, Page, Product, PromoCode, RentalPlan, Review, StoreSettings, Variant


class RentalPlanInline(admin.TabularInline):
    model = RentalPlan
    extra = 0


class AddOnInline(admin.TabularInline):
    model = AddOn
    extra = 0


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "buy_price", "was_price", "rent_rate", "rent_only", "stock", "rating", "review_count")
    list_filter = ("category", "brand", "rent_only", "free_delivery")
    search_fields = ("name", "slug", "description", "sku")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [VariantInline, RentalPlanInline, AddOnInline]
    readonly_fields = ("rating", "review_count")
    fieldsets = (
        (None, {"fields": ("name", "slug", "sku", "description", "category", "brand")}),
        ("Appearance", {"fields": ("kind", "bg")}),
        ("Pricing", {"fields": ("buy_price", "was_price", "rent_rate", "rent_only", "deposit")}),
        ("Stock & delivery", {"fields": ("stock", "ships_in_days", "free_delivery", "sold_percent")}),
        ("Details", {"fields": ("warranty", "specs", "in_the_box")}),
        ("Reviews (computed)", {"fields": ("rating", "review_count")}),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "title", "created_at")
    list_filter = ("rating",)
    search_fields = ("product__name", "user__name", "title", "body")

    def delete_queryset(self, request, queryset):
        products = {r.product for r in queryset}
        super().delete_queryset(request, queryset)
        for p in products:
            p.recompute_rating()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "kind", "sort")
    list_editable = ("sort",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 0


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("name", "sort")
    list_editable = ("sort",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BundleItemInline]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "active")
    list_editable = ("active",)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")
    search_fields = ("email",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "updated_at")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "topic", "name", "contact", "handled")
    list_filter = ("topic", "handled")
    list_editable = ("handled",)
    search_fields = ("name", "contact", "message")


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
