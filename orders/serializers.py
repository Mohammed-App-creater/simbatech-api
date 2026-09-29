from rest_framework import serializers

from accounts.identity import normalize_phone


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        phone = normalize_phone(super().to_internal_value(data))
        if not phone:
            raise serializers.ValidationError("Enter a valid phone number, e.g. 0911 234 567")
        return phone


class ContactSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, error_messages={"min_length": "Enter your full name", "required": "Enter your full name", "blank": "Enter your full name"})
    phone = PhoneField(error_messages={"required": "Enter your phone number", "blank": "Enter your phone number"})
    email = serializers.EmailField(error_messages={"invalid": "Enter a valid email address", "required": "Enter your email address", "blank": "Enter your email address"})


class NewAddressSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=30, required=False, allow_blank=True)
    line1 = serializers.CharField(min_length=3, error_messages={"min_length": "Enter the street and house", "required": "Enter the street and house", "blank": "Enter the street and house"})
    area = serializers.CharField(min_length=2, error_messages={"min_length": "Enter the area / sub-city", "required": "Enter the area / sub-city", "blank": "Enter the area / sub-city"})
    city = serializers.CharField(min_length=2, error_messages={"min_length": "Enter the city", "required": "Enter the city", "blank": "Enter the city"})
    phone = serializers.CharField(required=False, allow_blank=True)


class PaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["telebirr", "card", "cod"])
    phone = serializers.CharField(required=False, allow_blank=True)
    cardLast4 = serializers.RegexField(r"^\d{4}$", required=False, allow_blank=True)


class CheckoutSerializer(serializers.Serializer):
    contact = ContactSerializer()
    fulfilment = serializers.ChoiceField(choices=["delivery", "pickup"], default="delivery")
    addressId = serializers.CharField(required=False, allow_blank=True)
    newAddress = NewAddressSerializer(required=False)
    deliveryDate = serializers.DateField(required=False, error_messages={"invalid": "Use a yyyy-mm-dd date"})
    deliveryWindow = serializers.CharField(max_length=40, required=False, allow_blank=True)
    payment = PaymentSerializer()
    acceptTerms = serializers.BooleanField(error_messages={"required": "Please accept the terms to place your order"})

    def validate_acceptTerms(self, value):
        if not value:
            raise serializers.ValidationError("Please accept the terms to place your order")
        return value

    def validate(self, data):
        payment = data["payment"]
        if payment["method"] == "telebirr" and not normalize_phone(payment.get("phone")):
            raise serializers.ValidationError({"payment": {"phone": "Enter the phone number registered with Telebirr"}})
        return data


class ExtendSerializer(serializers.Serializer):
    days = serializers.IntegerField(required=False, default=1, min_value=1, max_value=30)


class StartPaymentSerializer(serializers.Serializer):
    orderId = serializers.CharField()


class ReviewSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, error_messages={"required": "Choose a star rating", "min_value": "Choose a star rating", "max_value": "Choose a star rating"})
    title = serializers.CharField(required=False, allow_blank=True, max_length=80)
    body = serializers.CharField(min_length=10, max_length=2000, error_messages={"min_length": "Tell us a little more (at least 10 characters)", "required": "Write your review", "blank": "Write your review"})


class ContactSerializer(serializers.Serializer):
    topic = serializers.ChoiceField(choices=["support", "sell", "careers", "other"], default="other")
    name = serializers.CharField(min_length=2, max_length=80, error_messages={"min_length": "Enter your name", "required": "Enter your name", "blank": "Enter your name"})
    contact = serializers.CharField(min_length=3, max_length=120, error_messages={"min_length": "Enter your phone or email", "required": "Enter your phone or email", "blank": "Enter your phone or email"})
    message = serializers.CharField(min_length=10, max_length=4000, error_messages={"min_length": "Tell us a little more (at least 10 characters)", "required": "Write your message", "blank": "Write your message"})
