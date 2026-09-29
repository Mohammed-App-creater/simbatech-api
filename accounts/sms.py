"""
Sending SMS. `console` logs the message (development); `africastalking` sends it for real.
"""

import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)


def sms_configured() -> bool:
    return settings.SMS_BACKEND == "africastalking" and bool(settings.AT_USERNAME and settings.AT_API_KEY)


def to_international(phone: str) -> str:
    """0911234567 -> +251911234567"""
    return "+251" + phone[1:] if phone.startswith("0") else phone


def send_sms(phone: str, message: str) -> None:
    if not sms_configured():
        log.info("SMS to %s: %s", phone, message)
        return
    payload = {"username": settings.AT_USERNAME, "to": to_international(phone), "message": message}
    if settings.AT_SENDER_ID:
        payload["from"] = settings.AT_SENDER_ID
    res = requests.post(
        "https://api.africastalking.com/version1/messaging",
        data=payload,
        headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"},
        timeout=15,
    )
    res.raise_for_status()
