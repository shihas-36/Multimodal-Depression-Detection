import os
from pathlib import Path
from decouple import config
import dj_database_url

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = config(
    'DJANGO_SECRET_KEY',
    default='django-insecure-dev-key-change-in-production'
)
DEBUG = config('DEBUG', default=False, cast=bool)

# Allowed Hosts
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS', 
    default='localhost,127.0.0.1,django',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
if os.environ.get("ALLOWED_HOSTS"):
    ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

# Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_celery_beat',
    'fl_core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files efficiently
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Priority: 1. DATABASE_URL, 2. DB_* env vars, 3. SQLite (local dev only)
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default=f"postgres://{config('DB_USER', default='postgres')}:{config('DB_PASSWORD', default='postgres')}@{config('DB_HOST', default='localhost')}:{config('DB_PORT', default='5432')}/{config('DB_NAME', default='federated_learning')}"),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=not DEBUG  # Require SSL in production
    )
}

# Use SQLite for development if DEBUG is True and no DATABASE_URL is provided
if DEBUG and not os.environ.get('DATABASE_URL'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

# Auth
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'fl_core.auth.DeviceAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# CORS
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost,http://127.0.0.1,http://192.168.1.3',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Celery & Redis
CELERY_BROKER_URL = os.environ.get('REDIS_URL', config('CELERY_BROKER_URL', default='redis://localhost:6379/0'))
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_RETRY = True

# Flower settings
FLOWER_SERVER_ADDRESS = config('FLOWER_SERVER_ADDRESS', default='127.0.0.1:8080')
FLOWER_NUM_ROUNDS = config('FLOWER_NUM_ROUNDS', default=5, cast=int)
FLOWER_MIN_CLIENTS = config('FLOWER_MIN_CLIENTS', default=3, cast=int)

# HTTPS & Proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Security headers (production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_SECURITY_POLICY = {
        'default-src': ("'self'",),
        'script-src': ("'self'",),
        'style-src': ("'self'", "'unsafe-inline'"),
    }

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': config('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'fl_core': {
            'handlers': ['console'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}
