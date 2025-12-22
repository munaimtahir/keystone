from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY","dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG","0") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS","*").split(",")

INSTALLED_APPS = [
  "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
  "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
  "corsheaders",
  "rest_framework",
  "rest_framework.authtoken",
  "api",
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

ROOT_URLCONF = "keystone.urls"
TEMPLATES = [{
  "BACKEND":"django.template.backends.django.DjangoTemplates",
  "DIRS":[], "APP_DIRS":True,
  "OPTIONS":{"context_processors":[
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
  ]},
}]
WSGI_APPLICATION = "keystone.wsgi.application"
DATABASES = {"default": dj_database_url.config(default=os.getenv("DATABASE_URL","sqlite:///db.sqlite3"))}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE="en-us"
TIME_ZONE="Asia/Karachi"
USE_I18N=True
USE_TZ=True

# Subpath deployment support
FORCE_SCRIPT_NAME = os.getenv("DJANGO_FORCE_SCRIPT_NAME", "")
STATIC_URL = f"{FORCE_SCRIPT_NAME}/static/" if FORCE_SCRIPT_NAME else "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"

# DRF: require auth by default (UI + API protected) and support token auth for SPA.
REST_FRAMEWORK = {
  "DEFAULT_AUTHENTICATION_CLASSES": [
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework.authentication.TokenAuthentication",
  ],
  "DEFAULT_PERMISSION_CLASSES": [
    "rest_framework.permissions.IsAuthenticated",
  ],
}

# CORS for the panel (served on :8080) to call API on :8000 in IP-mode MVP.
# Allow all origins in development, or specific origins in production
_cors = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
if _cors:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]
else:
    # In development/DEBUG mode, allow all origins for flexibility
    # In production, set CORS_ALLOWED_ORIGINS env var with specific origins
    CORS_ALLOWED_ORIGINS = []
    CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True
