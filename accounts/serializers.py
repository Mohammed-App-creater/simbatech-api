from rest_framework import serializers


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=80, error_messages={"min_length": "Enter your full name", "required": "Enter your full name", "blank": "Enter your full name"})
    identifier = serializers.CharField(min_length=3, error_messages={"min_length": "Enter your phone or email", "required": "Enter your phone or email", "blank": "Enter your phone or email"})
    password = serializers.CharField(
        min_length=8,
        max_length=128,
        trim_whitespace=False,
        error_messages={"min_length": "Use at least 8 characters for your password", "max_length": "That password is too long", "required": "Choose a password", "blank": "Choose a password"},
    )


class SigninSerializer(serializers.Serializer):
    identifier = serializers.CharField(min_length=3, error_messages={"min_length": "Enter your phone or email", "required": "Enter your phone or email", "blank": "Enter your phone or email"})
    password = serializers.CharField(trim_whitespace=False, error_messages={"required": "Enter your password", "blank": "Enter your password"})
    remember = serializers.BooleanField(required=False, default=True)


class AddressSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=30, error_messages={"required": "Give this address a name", "blank": "Give this address a name"})
    line1 = serializers.CharField(min_length=3, error_messages={"min_length": "Enter the street and house", "required": "Enter the street and house", "blank": "Enter the street and house"})
    area = serializers.CharField(min_length=2, error_messages={"min_length": "Enter the area / sub-city", "required": "Enter the area / sub-city", "blank": "Enter the area / sub-city"})
    city = serializers.CharField(min_length=2, error_messages={"min_length": "Enter the city", "required": "Enter the city", "blank": "Enter the city"})
    phone = serializers.CharField(error_messages={"required": "Enter a phone number", "blank": "Enter a phone number"})
    notes = serializers.CharField(max_length=200, required=False, allow_blank=True)
    isDefault = serializers.BooleanField(required=False)


class WishlistSerializer(serializers.Serializer):
    productId = serializers.CharField()
    saved = serializers.BooleanField()
