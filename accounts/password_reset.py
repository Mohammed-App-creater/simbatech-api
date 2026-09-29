"""
Forgot password: email accounts get a reset link by email; phone accounts get a code by SMS.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from core.errors import ApiError

from .models import OtpCode, User
from .otp import send_code, verify_code


def reset_link(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_ORIGIN}/reset-password?uid={uid}&token={token}"


def start_reset(ident: dict) -> dict:
    """Returns what the client should do next: {"via": "email"} or {"via": "sms", ...otp info}."""
    user = User.objects.filter(**ident).first()
    if "phone" in ident:
        if user:
            return {"via": "sms", **send_code(ident["phone"], OtpCode.Purpose.RESET)}
        # Don't reveal whether a number has an account; pretend to send.
        return {"via": "sms", "sent": True, "expiresInMinutes": settings.OTP_TTL_MINUTES, "resendInSeconds": 45}
    info = {"via": "email", "sent": True}
    if user:
        link = reset_link(user)
        send_mail(
            "Reset your Simbatech password",
            f"Hi {user.name},\n\nUse this link to choose a new password (it works for 3 days):\n{link}\n\nIf you didn't ask for this, you can ignore this email.",
            None,
            [user.email],
        )
        if settings.DEBUG and settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
            info["devLink"] = link  # no mail server in development: hand the link straight back
    return info


def finish_reset_by_token(uid: str, token: str, password: str) -> User:
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (ValueError, User.DoesNotExist):
        raise ApiError("That reset link isn't valid. Ask for a new one.", 400)
    if not default_token_generator.check_token(user, token):
        raise ApiError("That reset link has expired. Ask for a new one.", 400)
    user.set_password(password)
    user.save(update_fields=["password"])
    return user


def finish_reset_by_code(phone: str, code: str, password: str) -> User:
    user = User.objects.filter(phone=phone).first()
    if not user:
        raise ApiError("That code isn't right", 422, "code")
    verify_code(phone, OtpCode.Purpose.RESET, code)
    user.set_password(password)
    user.save(update_fields=["password"])
    return user
