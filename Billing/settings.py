import os
from pathlib import Path
import dj_database_url

# ==================================================
# BASE DIR
# ==================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================================================
# CORE SETTINGS
# ==================================================

SECRET_KEY = (
    os.getenv("DJANGO_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "unsafe-secret-key-change-me"
)

DEBUG = (
    os.getenv("DJANGO_DEBUG")
    or os.getenv("DEBUG", "False")
).lower() in ("1", "true", "yes", "y")

# --------------------------------------------------
# ALLOWED HOSTS
# --------------------------------------------------
_raw_hosts = (
    os.getenv("DJANGO_ALLOWED_HOSTS")
    or os.getenv("ALLOWED_HOSTS")
    or "127.0.0.1,localhost"
)

ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# --------------------------------------------------
# CSRF
# --------------------------------------------------
_raw_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _raw_csrf.split(",") if o.strip()]

# ==================================================
# APPLICATIONS
# ==================================================
INSTALLED_APPS = [
    "corsheaders",  # ✅ CORS

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
    "portal_api",
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
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # ✅ CORS MUST BE BEFORE CommonMiddleware
    "corsheaders.middleware.CorsMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# ==================================================
# CORS SETTINGS
# ==================================================
_raw_cors = os.getenv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()]

CORS_ALLOW_ALL_ORIGINS = (
    os.getenv("CORS_ALLOW_ALL_ORIGINS", "False")
    .lower() in ("1", "true", "yes", "y")
)

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
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,
            ssl_require=True,
        )
    }
else:
    if not DEBUG:
        raise RuntimeError(
            "DATABASE_URL missing in production. Refusing SQLite fallback."
        )

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
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

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
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000").strip()

PORTAL_API_BASE = os.getenv(
    "PORTAL_API_BASE",
    f"{SITE_URL}/api/portal/"
).strip()