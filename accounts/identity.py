import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def normalize_phone(raw: str | None) -> str | None:
    """Ethiopian mobile numbers normalised to the local 09XXXXXXXX / 07XXXXXXXX form."""
    d = re.sub(r"[^\d+]", "", raw or "")
    if d.startswith("+251"):
        d = "0" + d[4:]
    elif d.startswith("251") and len(d) == 12:
        d = "0" + d[3:]
    elif re.fullmatch(r"[79]\d{8}", d):
        d = "0" + d
    return d if re.fullmatch(r"0[79]\d{8}", d) else None


def parse_identifier(raw: str) -> dict | None:
    """The sign-in field accepts an email address or a phone number."""
    value = (raw or "").strip()
    if "@" in value:
        email = value.lower()
        try:
            validate_email(email)
        except ValidationError:
            return None
        return {"email": email}
    phone = normalize_phone(value)
    return {"phone": phone} if phone else None
