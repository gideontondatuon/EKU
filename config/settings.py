import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
PRODUCTION = ENVIRONMENT in {"production", "staging"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-only-not-for-production-" + "x" * 40)
if PRODUCTION and (
    SECRET_KEY.startswith(("local-only", "GANTI_", "change-me")) or len(SECRET_KEY) < 50
):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY wajib diisi secret acak minimal 50 karakter.")
DEBUG = not PRODUCTION and os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]
if os.getenv("VERCEL"):
    for host in [".vercel.app", "localhost", "127.0.0.1", "[::1]"]:
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)
    vercel_url = os.getenv("VERCEL_URL")
    if vercel_url and vercel_url not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_url)
    if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")
    if vercel_url:
        origin_url = f"https://{vercel_url}"
        if origin_url not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin_url)
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "core",
    "cashflow",
    "imports",
    "publications",
    "estimates",
    "dashboard",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.context.site_context",
            ]
        },
    }
]
db = urlparse(os.getenv("DATABASE_URL", "postgresql://eku@127.0.0.1:55432/eku"))
if db.scheme not in {"postgres", "postgresql"}:
    raise ImproperlyConfigured("Aplikasi dan tes memerlukan PostgreSQL.")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(db.path.lstrip("/")),
        "USER": unquote(db.username or ""),
        "PASSWORD": unquote(db.password or ""),
        "HOST": db.hostname or "localhost",
        "PORT": db.port or 5432,
        "CONN_MAX_AGE": 0 if os.getenv("VERCEL") else (60 if PRODUCTION else 0),
        "OPTIONS": {
            "sslmode": os.getenv("DATABASE_SSLMODE", "require" if os.getenv("VERCEL") else "prefer")
        },
    }
}
if PRODUCTION and not os.getenv("VERCEL") and (not os.getenv("DJANGO_ALLOWED_HOSTS") or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        "Production memerlukan DJANGO_ALLOWED_HOSTS eksplisit tanpa wildcard."
    )

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.UsernameEmailBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/"
LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Makassar"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
if os.getenv("VERCEL"):
    PRIVATE_ROOT = Path(os.getenv("PRIVATE_ROOT", "/tmp/.private"))
else:
    PRIVATE_ROOT = Path(os.getenv("PRIVATE_ROOT", str(BASE_DIR / ".private")))
MEDIA_ROOT = PRIVATE_ROOT / "uploads"
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_WORKBOOK_ROWS = 50000
MAX_WORKBOOK_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_SSL_REDIRECT = PRODUCTION
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = PRODUCTION
SECURE_HSTS_PRELOAD = PRODUCTION
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if os.getenv("TRUST_PROXY_SSL", "0") == "1" or os.getenv("VERCEL"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# A private DB-backed rate limiter works across Gunicorn workers; no process-local counter.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}

# Set only to a local static asset whose use has been approved by the owner.
BI_LOGO_STATIC_PATH = os.getenv("BI_LOGO_STATIC_PATH", "")
if BI_LOGO_STATIC_PATH and (
    BI_LOGO_STATIC_PATH.startswith("/")
    or ":" in BI_LOGO_STATIC_PATH
    or ".." in BI_LOGO_STATIC_PATH.split("/")
):
    raise ImproperlyConfigured("BI_LOGO_STATIC_PATH harus berupa path aset static lokal.")
