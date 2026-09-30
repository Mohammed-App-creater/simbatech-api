from rest_framework import serializers

# The illustrations the site can draw for a product (simbatech-web: src/components/Render.jsx).
KINDS = ["camera", "headphones", "sneaker", "sofa", "espresso", "drill", "tent", "watch", "skincare", "bike", "blocks", "phone"]

_price_msgs = {"invalid": "Enter a whole number of birr", "min_value": "Enter 0 or more", "required": "Enter a price", "null": "Enter a price"}


_percent_msgs = {"invalid": "Enter a percentage from 1 to 90", "min_value": "Enter a percentage from 1 to 90", "max_value": "Enter a percentage from 1 to 90"}
_text_msgs = {"blank": "This can't be left empty", "null": "This can't be left empty"}


def price_field(**kw):
    return serializers.IntegerField(min_value=0, max_value=100_000_000, error_messages=_price_msgs, **kw)


class OrderPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["PLACED", "PACKED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"], required=False)
    paymentStatus = serializers.ChoiceField(choices=["PENDING", "PAID", "FAILED", "REFUNDED"], required=False)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)


class RentalPatchSerializer(serializers.Serializer):
    rentalStatus = serializers.ChoiceField(choices=["SCHEDULED", "ACTIVE", "RETURNED"])


class ReviewPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "approved", "rejected"])


class MessagePatchSerializer(serializers.Serializer):
    handled = serializers.BooleanField()


class PromoSerializer(serializers.Serializer):
    code = serializers.RegexField(
        r"^[A-Za-z0-9_-]{3,30}$",
        error_messages={"invalid": "Use 3–30 letters, digits, - or _", "required": "Enter a code", "blank": "Enter a code"},
    )
    percentOff = serializers.IntegerField(min_value=1, max_value=90, error_messages={**_percent_msgs, "required": "Enter the percentage off", "null": "Enter the percentage off"})
    active = serializers.BooleanField(required=False, default=True)


class PromoPatchSerializer(serializers.Serializer):
    percentOff = serializers.IntegerField(min_value=1, max_value=90, required=False, error_messages=_percent_msgs)
    active = serializers.BooleanField(required=False)


class PlanSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=365, error_messages={"invalid": "Enter the number of days", "min_value": "Enter 1 day or more", "required": "Enter the number of days"})
    price = price_field()


class AddOnSerializer(serializers.Serializer):
    key = serializers.SlugField(required=False, allow_blank=True)
    label = serializers.CharField(max_length=60, error_messages={"required": "Name the add-on", "blank": "Name the add-on"})
    note = serializers.CharField(max_length=120, required=False, allow_blank=True)
    perDay = price_field()


class VariantSerializer(serializers.Serializer):
    key = serializers.SlugField(required=False, allow_blank=True)
    label = serializers.CharField(max_length=60, error_messages={"required": "Name the option", "blank": "Name the option"})
    extra = price_field(required=False, default=0)


class ProductSerializer(serializers.Serializer):
    """Create: every field without a default is needed. Edit: send only what changes (partial=True)."""

    name = serializers.CharField(min_length=2, max_length=120, error_messages={"min_length": "Enter the product name", "required": "Enter the product name", "blank": "Enter the product name"})
    description = serializers.CharField(max_length=4000, error_messages={"required": "Describe the product", "blank": "Describe the product"})
    category = serializers.SlugField(error_messages={"required": "Choose a category", "blank": "Choose a category"})
    brand = serializers.SlugField(error_messages={"required": "Choose a brand", "blank": "Choose a brand"})
    kind = serializers.ChoiceField(choices=KINDS, error_messages={"required": "Choose a picture", "invalid_choice": "Choose a picture"})
    bg = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", error_messages={"invalid": "Use a colour like #E0F1FF", "required": "Choose a background colour"})
    sku = serializers.CharField(max_length=40, required=False, allow_blank=True)
    buyPrice = price_field()
    wasPrice = price_field(required=False, allow_null=True)
    rentRate = price_field(required=False, allow_null=True)
    rentOnly = serializers.BooleanField(required=False)
    deposit = price_field(required=False)
    stock = serializers.IntegerField(min_value=0, max_value=1_000_000, required=False, error_messages={"invalid": "Enter a whole number", "min_value": "Enter 0 or more"})
    soldPercent = serializers.IntegerField(min_value=0, max_value=100, required=False, error_messages={"invalid": "Enter 0 to 100", "min_value": "Enter 0 to 100", "max_value": "Enter 0 to 100"})
    freeDelivery = serializers.BooleanField(required=False)
    shipsInDays = serializers.IntegerField(min_value=1, max_value=365, required=False, allow_null=True, error_messages={"invalid": "Enter a number of days", "min_value": "Enter 1 day or more"})
    warranty = serializers.CharField(max_length=60, required=False, allow_blank=True)
    specs = serializers.ListField(child=serializers.ListField(child=serializers.CharField(max_length=200), min_length=2, max_length=2), required=False, max_length=40)
    inTheBox = serializers.ListField(child=serializers.CharField(max_length=120), required=False, max_length=40)
    plans = PlanSerializer(many=True, required=False)
    addOns = AddOnSerializer(many=True, required=False)
    variants = VariantSerializer(many=True, required=False)


class StoreSettingsSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, required=False, error_messages=_text_msgs)
    city = serializers.CharField(max_length=60, required=False, error_messages=_text_msgs)
    address = serializers.CharField(max_length=160, required=False, error_messages=_text_msgs)
    phone = serializers.CharField(max_length=20, required=False, error_messages=_text_msgs)
    whatsapp = serializers.CharField(max_length=20, required=False, error_messages=_text_msgs)
    email = serializers.EmailField(required=False, error_messages={**_text_msgs, "invalid": "Enter a valid email address"})
    hours = serializers.CharField(max_length=60, required=False, error_messages=_text_msgs)
    sameDayCutoffHour = serializers.IntegerField(min_value=0, max_value=23, required=False, error_messages={"null": "Enter an hour from 0 to 23", "invalid": "Enter an hour from 0 to 23", "min_value": "Enter an hour from 0 to 23", "max_value": "Enter an hour from 0 to 23"})
    pickupReadyHours = serializers.IntegerField(min_value=0, max_value=240, required=False, error_messages={"null": "Enter a number of hours", "invalid": "Enter a number of hours"})
    returnDays = serializers.IntegerField(min_value=0, max_value=365, required=False, error_messages={"null": "Enter a number of days", "invalid": "Enter a number of days"})
    depositRefundDays = serializers.IntegerField(min_value=0, max_value=365, required=False, error_messages={"null": "Enter a number of days", "invalid": "Enter a number of days"})
    warranty = serializers.CharField(max_length=60, required=False, error_messages=_text_msgs)
    damagePolicy = serializers.CharField(max_length=200, required=False, error_messages=_text_msgs)
    payOnDeliveryTerms = serializers.CharField(max_length=200, required=False, error_messages=_text_msgs)
