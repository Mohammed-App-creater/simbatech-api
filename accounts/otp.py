"""One-time codes by SMS, for phone sign-in and password reset."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from core.errors import ApiError

from .models import OtpCode
from .sms import send_sms, sms_configured

MAX_ATTEMPTS = 5
RESEND_SECONDS = 45


def send_code(phone: str, purpose: str) -> dict:
    """Creates a fresh code (invalidating earlier ones) and sends it. Returns info for the client."""
    now = timezone.now()
    last = OtpCode.objects.filter(phone=phone, purpose=purpose, used=False).first()
    if last and (now - last.created_at).total_seconds() < RESEND_SECONDS:
        raise ApiError(f"Please wait {RESEND_SECONDS} seconds before asking for another code", 429)
    OtpCode.objects.filter(phone=phone, purpose=purpose, used=False).update(used=True)

    code = f"{secrets.randbelow(1_000_000):06d}"
    OtpCode.objects.create(phone=phone, purpose=purpose, code_hash=make_password(code), expires_at=now + timedelta(minutes=settings.OTP_TTL_MINUTES))
    what = "sign in to" if purpose == OtpCode.Purpose.LOGIN else "reset your password on"
    send_sms(phone, f"{code} is your code to {what} Simbatech. It expires in {settings.OTP_TTL_MINUTES} minutes.")

    info = {"sent": True, "expiresInMinutes": settings.OTP_TTL_MINUTES, "resendInSeconds": RESEND_SECONDS}
    if settings.DEBUG and not sms_configured():
        info["devCode"] = code  # no SMS provider in development: hand the code straight back
    return info


def verify_code(phone: str, purpose: str, code: str) -> None:
    """Raises ApiError if the code is wrong; marks it used when right."""
    entry = OtpCode.objects.filter(phone=phone, purpose=purpose, used=False).first()
    if not entry or entry.expires_at < timezone.now():
        raise ApiError("That code has expired. Ask for a new one.", 422, "code")
    if entry.attempts >= MAX_ATTEMPTS:
        raise ApiError("Too many wrong attempts. Ask for a new code.", 422, "code")
    if not check_password(code.strip(), entry.code_hash):
        entry.attempts += 1
        entry.save(update_fields=["attempts"])
        raise ApiError("That code isn't right", 422, "code")
    entry.used = True
    entry.save(update_fields=["used"])
