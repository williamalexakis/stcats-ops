from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages"
            ]
        }
    }
]

# Env stuff
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = [host.strip() for host in env("ALLOWED_HOSTS", default="").split(",") if host.strip()]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in env("CSRF_TRUSTED_ORIGINS", default="").split(",")
    if origin.strip()
]

DATABASES = {"default": env.db("DATABASE_URL")}

TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.AuditMiddleware"
]

ROOT_URLCONF = "stcats_cs.urls"
WSGI_APPLICATION = "stcats_cs.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    }
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Athens"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_SECURE_DEFAULT = not DEBUG

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=_SECURE_DEFAULT)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS",
    default=31536000 if _SECURE_DEFAULT else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=_SECURE_DEFAULT
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=_SECURE_DEFAULT)
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", default="strict-origin")
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("SECURE_CONTENT_TYPE_NOSNIFF", default=True)

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=_SECURE_DEFAULT)
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Strict")

CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=_SECURE_DEFAULT)
CSRF_COOKIE_HTTPONLY = env.bool("CSRF_COOKIE_HTTPONLY", default=True)
CSRF_COOKIE_SAMESITE = env("CSRF_COOKIE_SAMESITE", default="Strict")
