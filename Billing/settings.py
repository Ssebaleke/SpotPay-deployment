import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# ==================================================
# BASE DIR & ENV
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# .env is one level above billing-system (SpotPay/.env)
load_dotenv(BASE_DIR.parent / ".env")

# ==================================================
# CORE SETTINGS
# ==================================================

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-secret-key-change-me")

DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS", "127.0.0.1,localhost"
).split(",")

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
    "portal_api",          # safer than portal_api.apps.PortalApiConfig
    "vouchers",
    "wallets",
    "sms",
    "payments",
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
# DATABASE
# ==================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,      # good for poolers
            ssl_require=True,
        )
    }

    # psycopg3 pooler safe options
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].update({
        "prepare_threshold": 0,
    })

else:
    # Fallback to SQLite (local development)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ==================================================
# PASSWORD VALIDATION
# ==================================================

AUTH_PASSWORD_VALIDATORS = []

# ==================================================
# SESSIONS
# ==================================================

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# ==================================================
# INTERNATIONALIZATION
# ==================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ==================================================
# STATIC & MEDIA
# ==================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ==================================================
# EMAIL (DEV)
# ==================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ==================================================
# DEFAULT FIELD
# ==================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==================================================
# PROJECT CONSTANTS
# ==================================================

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")
PORTAL_API_BASE = os.getenv(
    "PORTAL_API_BASE",
    "http://127.0.0.1:8000/api/portal/"
)
