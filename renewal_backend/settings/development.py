"""
Development settings for Intelipro Insurance Policy Renewal System.
"""

from .base import *
from decouple import config
from django.conf import settings

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,0.0.0.0,testserver,13.233.6.207',
    cast=lambda v: [s.strip() for s in v.split(',')],
    
)
ALLOWED_HOSTS.append('.ngrok-free.dev')
ALLOWED_HOSTS.append('overgrossly-sugarlike-xuan.ngrok-free.dev')
# Development-specific apps
INSTALLED_APPS += [
    
]

if DEBUG:
    INSTALLED_APPS += [
        # 'django_debug_toolbar',  # Add when needed
    ]
    
    # MIDDLEWARE += [
    #     'debug_toolbar.middleware.DebugToolbarMiddleware',
    # ]
    
    # Debug Toolbar Configuration
    # INTERNAL_IPS = [
    #     '127.0.0.1',
    #     'localhost',
    # ]
    
    # DEBUG_TOOLBAR_CONFIG = {
    #     'DISABLE_PANELS': [
    #         'debug_toolbar.panels.redirects.RedirectsPanel',
    #     ],
    #     'SHOW_TEMPLATE_CONTEXT': True,
    # }

# Email backend for development
# Use console backend only if no EMAIL_HOST_USER is configured
# This allows testing real email sending when SMTP credentials are provided
# print(f"DEBUG: EMAIL_HOST_USER is: [ {config('EMAIL_HOST_USER', default='IS-NOT-SET')} ]")
if not settings.EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    print("📧 Using console email backend (emails will appear in terminal)")
else:
    # Use SMTP backend when credentials are provided
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    print("📧 Using SMTP email backend (emails will be sent via SMTP)")

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True

# Security settings for development
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Cache settings for development
# Override cache configuration for development with a proper cache backend
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 60,  # Shorter cache timeout for development
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}


# Celery settings for development
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'


# Logging for development
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['renewal_backend']['level'] = 'DEBUG'

# File storage for development (local)
if not config('AWS_ACCESS_KEY_ID', default=None):
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# Development database settings (SQLite doesn't need these options)
# DATABASES['default']['OPTIONS'] = {
#     'connect_timeout': 10,
# }

print("🚀 Running in DEVELOPMENT mode")
print(f"📊 Debug mode: {DEBUG}")
print(f"🔗 Allowed hosts: {ALLOWED_HOSTS}")
print(f"📧 Email backend: {EMAIL_BACKEND}")
print(f"💾 File storage: {DEFAULT_FILE_STORAGE if 'DEFAULT_FILE_STORAGE' in locals() else 'AWS S3'}") 