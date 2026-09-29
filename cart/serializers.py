from rest_framework import serializers


class AddToCartSerializer(serializers.Serializer):
    productId = serializers.CharField()
    mode = serializers.ChoiceField(choices=["buy", "rent"])
    qty = serializers.IntegerField(required=False, min_value=1, max_value=20)
    rentStart = serializers.DateField(required=False, error_messages={"invalid": "Use a yyyy-mm-dd date"})
    rentDays = serializers.IntegerField(required=False, min_value=1, max_value=90)
    addOns = serializers.ListField(child=serializers.CharField(), required=False, max_length=10)


class UpdateCartItemSerializer(serializers.Serializer):
    qty = serializers.IntegerField(required=False, min_value=1, max_value=20)
    rentStart = serializers.DateField(required=False, error_messages={"invalid": "Use a yyyy-mm-dd date"})
    rentDays = serializers.IntegerField(required=False, min_value=1, max_value=90)
    addOns = serializers.ListField(child=serializers.CharField(), required=False, max_length=10)
    savedForLater = serializers.BooleanField(required=False)


class PromoSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=30, error_messages={"required": "Enter a promo code", "blank": "Enter a promo code"})
