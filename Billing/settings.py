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

# ==================================================
# ALLOWED HOSTS
# ==================================================
_raw_hosts = (
    os.getenv("DJANGO_ALLOWED_HOSTS")
    or os.getenv("ALLOWED_HOSTS")
    or "127.0.0.1,localhost"
)

ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# ==================================================
# CSRF TRUSTED ORIGINS
# ==================================================
_raw_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _raw_csrf.split(",") if o.strip()]

# ==================================================
# APPLICATIONS
# ==================================================
INSTALLED_APPS = [
    "corsheaders",

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
    "analytics",
    "hotspot",
    "packages",
    "portal_api",
    "vouchers",
    "wallets",
    "sms",
    "payments",
    "mikrotik",
]

# ==================================================
# MIDDLEWARE
# ==================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # CORS must be high
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
# Must allow ALL origins — captive portal is served from MikroTik DNS
# (e.g. http://hot.spot) which is always a different origin from the API.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = False

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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
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
        raise RuntimeError("DATABASE_URL missing in production. Refusing SQLite fallback.")
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
SESSION_SAVE_EVERY_REQUEST = True

# ==================================================
# INTERNATIONALIZATION
# ==================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

# ==================================================
# STATIC
# ==================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ==================================================
# MEDIA (Uploads)
# ==================================================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ==================================================
# UPLOAD LIMITS (IMPORTANT FOR VIDEO)
# Default Django can choke on big files if your proxy/container limits are small.
# ==================================================
# 200MB (adjust if you need bigger)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(200 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(200 * 1024 * 1024)))

# If you upload large videos, better to stream to disk
FILE_UPLOAD_TEMP_DIR = os.getenv("FILE_UPLOAD_TEMP_DIR", None)

# ==================================================
# EMAIL
# ==================================================
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# ==================================================
# CACHE (Redis — shared across all gunicorn workers)
# ==================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://redis:6379/1"),
    }
}

# ==================================================
# DEFAULT FIELD
# ==================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==================================================
# PROJECT CONSTANTS
# ==================================================
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000").strip().rstrip("/")

# IMPORTANT: keep it WITHOUT trailing slash to avoid double paths
PORTAL_API_BASE = os.getenv("PORTAL_API_BASE", f"{SITE_URL}/api/portal").strip().rstrip("/")

# HTTP version for captive portal — devices behind walled garden can't verify SSL
# Use server IP or HTTP URL so devices connect without cert errors
_site_url_http = SITE_URL.replace("https://", "http://")
PORTAL_API_BASE_HTTP = os.getenv("PORTAL_API_BASE_HTTP", f"{_site_url_http}/api/portal").strip().rstrip("/")

# ==================================================
# MIKHMON
# ==================================================
MIKHMON_URL = os.getenv("MIKHMON_URL", "").strip().rstrip("/")
MIKHMON_USER = os.getenv("MIKHMON_USER", "admin")
MIKHMON_PASS = os.getenv("MIKHMON_PASS", "")

# ==================================================
# WIREGUARD VPN
# ==================================================
VPN_SERVER_IP = os.getenv("VPN_SERVER_IP", "").strip()
VPN_SERVER_PORT = os.getenv("VPN_SERVER_PORT", "51820").strip()
VPN_SERVER_PUBLIC_KEY = os.getenv("VPN_SERVER_PUBLIC_KEY", "").strip()
VPN_INTERFACE_NAME = os.getenv("VPN_INTERFACE_NAME", "wg0").strip()
VPN_SUBNET = os.getenv("VPN_SUBNET", "10.10.0").strip()

# ==================================================
# VPS SSH (Mikhmon auto-config)
# ==================================================
VPS_SSH_HOST = os.getenv("VPS_SSH_HOST", "").strip()
VPS_SSH_USER = os.getenv("VPS_SSH_USER", "root").strip()
VPS_SSH_PASS = os.getenv("VPS_SSH_PASS", "").strip()
MIKHMON_CONFIG_PATH = os.getenv("MIKHMON_CONFIG_PATH", "/root/mikhmon-v3/include/config.php").strip()

# ==================================================
# PROXY / HTTPS (safe defaults; won't break HTTP)
# If you're behind nginx later, these help correct scheme/secure cookies
# ==================================================
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")