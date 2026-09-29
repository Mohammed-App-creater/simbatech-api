"""
Sign in with Google (OAuth 2.0 authorization code flow).

Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET and register
`<API_PUBLIC_URL>/api/auth/google/callback` as an authorised redirect URI.
"""

import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings

from core.errors import ApiError

from .models import User

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_KEY = "google_oauth_state"
NEXT_KEY = "google_oauth_next"


def google_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return f"{settings.API_PUBLIC_URL}/api/auth/google/callback"


def start_url(request, next_path: str) -> str:
    state = secrets.token_urlsafe(24)
    request.session[STATE_KEY] = state
    request.session[NEXT_KEY] = next_path
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def finish(request, code: str, state: str) -> User:
    """Exchanges the code, then finds or creates the matching user."""
    if not state or state != request.session.pop(STATE_KEY, None):
        raise ApiError("Sign-in with Google didn't complete. Please try again.", 400)
    token = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if not token.ok:
        raise ApiError("Google didn't accept the sign-in. Please try again.", 400)
    info = requests.get(USERINFO_URL, headers={"Authorization": "Bearer " + token.json()["access_token"]}, timeout=15).json()
    sub, email = info.get("sub"), (info.get("email") or "").lower()
    if not sub or not email or not info.get("email_verified", True):
        raise ApiError("We couldn't get a verified email address from Google.", 400)

    user = User.objects.filter(google_sub=sub).first() or User.objects.filter(email=email).first()
    if user:
        if not user.google_sub:
            user.google_sub = sub
            user.save(update_fields=["google_sub"])
        return user
    return User.objects.create_user(name=info.get("name") or email.split("@")[0], email=email, google_sub=sub)
