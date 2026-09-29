"""
Django settings for the Simbatech API.

Configuration comes from environment variables (see .env.example). Defaults are for local
development only.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,api").split(",") if h.strip()]

# The Next.js site(s) that talk to this API (browser requests are proxied through them). A comma-separated
# list is accepted; the first entry is where sign-in and payment redirects send the customer.
FRONTEND_ORIGINS = [o.strip().rstrip("/") for o in os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",") if o.strip()]
FRONTEND_ORIGIN = FRONTEND_ORIGINS[0]
CSRF_TRUSTED_ORIGINS = FRONTEND_ORIGINS
CORS_ALLOWED_ORIGINS = FRONTEND_ORIGINS
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "accounts",
    "catalog",
    "cart",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


def _database_from_url(url: str) -> dict:
    u = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": u.username,
        "PASSWORD": u.password,
        "HOST": u.hostname,
        "PORT": u.port or 5432,
        "CONN_MAX_AGE": 60,
    }


DATABASES = {"default": _database_from_url(os.environ.get("DATABASE_URL", "postgresql://simbatech:simbatech@localhost:5432/simbatech"))}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "core.errors.exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# Sessions hold both the login and the guest cart; the cookie lives 30 days unless "remember me" is off.
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_DAYS", "30")) * 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Addis_Ababa"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Integrations (all optional; without keys the API runs in a development mode) ──

# Payments: Chapa (https://chapa.co) hosts the payment page and supports Telebirr, CBE Birr and cards.
CHAPA_SECRET_KEY = os.environ.get("CHAPA_SECRET_KEY", "")
CHAPA_WEBHOOK_SECRET = os.environ.get("CHAPA_WEBHOOK_SECRET", "")
# Where the API itself is reachable from the internet (Chapa redirects the customer back here).
API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "http://localhost:8000")

# Google sign-in (OAuth client of type "Web application"; redirect URI = API_PUBLIC_URL + /api/auth/google/callback)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# SMS for one-time codes: "console" (printed to the log; the API also returns the code while DEBUG)
# or "africastalking" (AT_USERNAME + AT_API_KEY, optional AT_SENDER_ID).
SMS_BACKEND = os.environ.get("SMS_BACKEND", "console")
AT_USERNAME = os.environ.get("AT_USERNAME", "")
AT_API_KEY = os.environ.get("AT_API_KEY", "")
AT_SENDER_ID = os.environ.get("AT_SENDER_ID", "")
OTP_TTL_MINUTES = 10

# Email for password-reset links: SMTP when EMAIL_HOST is set, otherwise printed to the log.
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Simbatech <no-reply@simbatech.et>")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
