from rest_framework import serializers

_id_msgs = {"min_length": "Enter your phone or email", "required": "Enter your phone or email", "blank": "Enter your phone or email"}
_name_msgs = {"min_length": "Enter your full name", "required": "Enter your full name", "blank": "Enter your full name"}
_pw_msgs = {"min_length": "Use at least 8 characters for your password", "max_length": "That password is too long", "required": "Choose a password", "blank": "Choose a password"}


def password_field(**kw):
    return serializers.CharField(min_length=8, max_length=128, trim_whitespace=False, error_messages=_pw_msgs, **kw)


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=80, error_messages=_name_msgs)
    identifier = serializers.CharField(min_length=3, error_messages=_id_msgs)
    password = password_field()


class SigninSerializer(serializers.Serializer):
    identifier = serializers.CharField(min_length=3, error_messages=_id_msgs)
    password = serializers.CharField(trim_whitespace=False, error_messages={"required": "Enter your password", "blank": "Enter your password"})
    remember = serializers.BooleanField(required=False, default=True)


class OtpSendSerializer(serializers.Serializer):
    phone = serializers.CharField(error_messages={"required": "Enter your phone number", "blank": "Enter your phone number"})


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(error_messages={"required": "Enter your phone number", "blank": "Enter your phone number"})
    code = serializers.CharField(min_length=4, max_length=8, error_messages={"required": "Enter the code we sent you", "blank": "Enter the code we sent you", "min_length": "Enter the 6-digit code"})
    name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    remember = serializers.BooleanField(required=False, default=True)


class ForgotPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField(min_length=3, error_messages=_id_msgs)


class ResetPasswordSerializer(serializers.Serializer):
    # either uid + token (email link) or phone + code (SMS)
    uid = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    password = password_field()

    def validate(self, data):
        if not ((data.get("uid") and data.get("token")) or (data.get("phone") and data.get("code"))):
            raise serializers.ValidationError("That reset link isn't valid. Ask for a new one.")
        return data


class ChangePasswordSerializer(serializers.Serializer):
    current = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    password = password_field()


class ProfileSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=80, required=False, error_messages=_name_msgs)
    email = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class NotificationPrefsSerializer(serializers.Serializer):
    sms = serializers.BooleanField(required=False)
    email = serializers.BooleanField(required=False)
    remind = serializers.BooleanField(required=False)
    deals = serializers.BooleanField(required=False)


class PaymentMethodSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["telebirr", "card"])
    label = serializers.CharField(required=False, allow_blank=True, max_length=40)
    phone = serializers.CharField(required=False, allow_blank=True)
    brand = serializers.ChoiceField(choices=["Visa", "Mastercard"], required=False)
    last4 = serializers.RegexField(r"^\d{4}$", required=False, error_messages={"invalid": "Enter the last 4 digits of the card"})
    expiry = serializers.RegexField(r"^(0[1-9]|1[0-2])/\d{2}$", required=False, error_messages={"invalid": "Enter the expiry as MM/YY"})
    holder = serializers.CharField(required=False, allow_blank=True, max_length=80)
    isDefault = serializers.BooleanField(required=False)

    def validate(self, data):
        if data["kind"] == "telebirr" and not data.get("phone"):
            raise serializers.ValidationError({"phone": "Enter the Telebirr phone number"})
        if data["kind"] == "card" and not (data.get("brand") and data.get("last4") and data.get("expiry")):
            raise serializers.ValidationError({"last4": "Enter the card brand, last 4 digits and expiry"})
        return data


class PaymentMethodPatchSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, allow_blank=True, max_length=40)
    isDefault = serializers.BooleanField(required=False)


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
