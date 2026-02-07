import os
from pathlib import Path

from dotenv import load_dotenv
import dj_database_url

# ==================================================
# BASE DIR & ENV
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# .env is located at: SpotPay/.env  (one level above Billing/)
load_dotenv(BASE_DIR.parent / ".env")

# ==================================================
# CORE SETTINGS
# ==================================================

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-secret-key-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes", "y")

# Allow comma-separated hosts from .env OR fall back to localhost
_env_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _env_hosts.split(",") if h.strip()]

# ==================================================
# APPLICATIONS
# ==================================================

INSTALLED_APPS = [
    "widget_tweaks",
    "django.contrib.humanize",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "accounts",
    "ads",
    "hotspot",
    "packages",
    "payments",
    "portal_api.apps.PortalApiConfig",
    "vouchers",
    "wallets",
    "sms.apps.SmsConfig",
]

# ==================================================
# MIDDLEWARE
# ==================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# ==================================================
# URL / WSGI
# ==================================================

ROOT_URLCONF = "Billing.urls"
WSGI_APPLICATION = "Billing.wsgi.application"

# ==================================================
# TEMPLATES
# ==================================================

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

# ==================================================
# DATABASE — SUPABASE TRANSACTION POOLER (IMPORTANT)
# ==================================================
# Transaction pooler prefers short-lived connections:
# - conn_max_age=0 prevents keeping connections open
# - prepare_threshold=0 disables prepared statements (needed for poolers)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Put it in SpotPay/.env")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0,       # IMPORTANT for transaction pooler
        ssl_require=True,
    )
}

# Psycopg3-specific options for poolers (safe to keep)
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"].update({
    "prepare_threshold": 0,  # disables prepared statements
})

# ==================================================
# AUTH / SESSIONS
# ==================================================

AUTH_PASSWORD_VALIDATORS = []

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# ==================================================
# I18N / TIME
# ==================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ==================================================
# STATIC & MEDIA
# ==================================================

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ==================================================
# EMAIL (DEV)
# ==================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ==================================================
# PROJECT CONSTANTS
# ==================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")
PORTAL_API_BASE = os.getenv("PORTAL_API_BASE", "http://127.0.0.1:8000/api/portal/")
