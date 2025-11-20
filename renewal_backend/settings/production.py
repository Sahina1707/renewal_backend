"""
Production settings for Intelipro Insurance Policy Renewal System.
"""

from .base import *
from decouple import config
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,0.0.0.0,testserver,13.233.6.207',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Security settings for production
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Session and CSRF security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

# X-Frame-Options
X_FRAME_OPTIONS = 'DENY'

# CORS settings for production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

# Database settings for production
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': 60,
    'options': '-c default_transaction_isolation=serializable',
    'sslmode': 'disable',
}

# Connection pooling for production
DATABASES['default']['CONN_MAX_AGE'] = 600

# Static files configuration for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# File storage for production (AWS S3)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Cache settings for production - Redis configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'intelipro_renewal',
        'TIMEOUT': 300,
    }
}

# Email settings for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Celery settings for production
CELERY_TASK_ALWAYS_EAGER = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Logging for production
LOGGING['handlers']['file']['level'] = 'WARNING'
LOGGING['handlers']['console']['level'] = 'ERROR'
LOGGING['loggers']['django']['level'] = 'WARNING'
LOGGING['loggers']['renewal_backend']['level'] = 'INFO'

# Add additional logging handlers for production
LOGGING['handlers']['error_file'] = {
    'level': 'ERROR',
    'class': 'logging.FileHandler',
    'filename': config('ERROR_LOG_FILE', default='logs/error.log'),
    'formatter': 'verbose',
}

LOGGING['handlers']['security_file'] = {
    'level': 'INFO',
    'class': 'logging.FileHandler',
    'filename': config('SECURITY_LOG_FILE', default='logs/security.log'),
    'formatter': 'verbose',
}

# Add security logging
LOGGING['loggers']['django.security'] = {
    'handlers': ['security_file', 'console'],
    'level': 'INFO',
    'propagate': False,
}

# Sentry configuration for error tracking
SENTRY_DSN = config('SENTRY_DSN', default=None)
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_spans=True,
                signals_spans=True,
                cache_spans=True,
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,
                propagate_traces=True,
            ),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
        release=config('RELEASE_VERSION', default='1.0.0'),
    )

# Performance optimizations
CONN_MAX_AGE = 600  # Database connection pooling

# Rate limiting for production
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Additional security headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Admin security
ADMIN_URL = config('ADMIN_URL', default='admin/')

print("🔒 Running in PRODUCTION mode")
print(f"🛡️  Security features enabled")
print(f"📊 Sentry monitoring: {'✅' if SENTRY_DSN else '❌'}")
print(f"💾 File storage: AWS S3")
print(f"🔐 SSL redirect: {SECURE_SSL_REDIRECT}") 
