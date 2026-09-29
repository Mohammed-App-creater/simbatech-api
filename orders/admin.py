from django.contrib import admin

from .models import Order, OrderEvent, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "name", "mode", "qty", "unit_price", "line_total", "rent_start", "rent_end", "rent_days", "deposit")
    fields = readonly_fields + ("rental_status", "extended_days", "extra_charge")


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Staff update an order's status here (the customer's tracking timeline follows it).
    Add an event with the new status so the timeline shows when it happened.
    """

    list_display = ("number", "created_at", "contact_name", "status", "payment_method", "payment_status", "total")
    list_filter = ("status", "payment_status", "payment_method", "fulfilment")
    search_fields = ("number", "contact_name", "contact_phone", "contact_email")
    readonly_fields = ("id", "number", "created_at", "purchases_total", "rentals_total", "delivery_fee", "discount", "deposit_total", "total", "promo_code")
    inlines = [OrderItemInline, OrderEventInline]
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # keep the timeline in step with a status change made on the order itself
        if change and "status" in form.changed_data:
            OrderEvent.objects.create(order=obj, status=obj.status, note="Updated by staff")
