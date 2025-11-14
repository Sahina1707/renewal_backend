"""
Base settings for Intelipro Insurance Policy Renewal System.
This contains common settings shared across all environments.
"""

import os
from pathlib import Path
from decouple import config
from datetime import timedelta
from celery.schedules import crontab
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# Application definition
DJANGO_APPS = [
    'daphne',  # ASGI server for channels
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',
    'django_celery_beat',  # Add when Celery is installed
    # 'django_celery_results',  # Add when Celery is installed
    'drf_spectacular',
    'django_extensions',
    'django_filters',
    'storages',
]

LOCAL_APPS = [
    'apps.core',
    'apps.users',
    'apps.authentication',
    'apps.customers',
    'apps.policies',
    'apps.uploads',
    'apps.campaigns',
    'apps.templates', 'apps.target_audience',
    'apps.policy_data',
    'apps.files_upload',
    'apps.renewals',
    'apps.channels',
    'apps.distribution_channel',
    'apps.hierarchy',
    'apps.case_tracking',
    'apps.case_logs',
    'apps.case_details',
    'apps.case_history',
    'apps.closed_cases',
    'apps.customer_financial_profile',
    'apps.customer_assets',
    'apps.customer_vehicle',
    'apps.customer_policy_preferences',
    'apps.customer_family_medical_history',
    'apps.customer_payments',
    'apps.customer_payment_schedule',
    'apps.customer_communication_preferences',
    'apps.customers_files',
    'apps.ai_insights',
    'apps.claims',
    'apps.campaign_manager',
    'apps.audience_manager',
    'apps.customer_insights',
    'apps.ai_policy_recommendations',
    'apps.policy_timeline',
    'apps.other_insurance_policies',
    'apps.policy_features',
    'apps.policy_additional_benefits',
    'apps.policy_coverages',
    'apps.policy_exclusions',
    'apps.policy_conditions',
    'apps.renewal_timeline',
    'apps.email_provider',
    'apps.email_templates',
    'apps.email_operations',
    'apps.email_inbox',
    'apps.email_integration',
    'apps.email_manager',
    'apps.whatsapp_provider',
    'apps.offers',
    'apps.customer_installment',
    'apps.outstanding_amounts',
    'apps.dashboard',
    'apps.upload_chatbot',
    'apps.case_tracking_chatbot',
    'apps.closed_case_chatbot',
    'apps.policytimeline_chatbot',
    'apps.case_logs_chatbot',
    'apps.verification',
    # 'apps.communications',
    # 'apps.emails',
    # 'apps.surveys',
    # 'apps.claims',
    # 'apps.notifications',
    # 'apps.analytics',
    # 'apps.files',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.RequestLoggingMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
]

ROOT_URLCONF = 'renewal_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'renewal_backend.wsgi.application'
ASGI_APPLICATION = 'renewal_backend.asgi.application'

# Database Configuration
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# PostgreSQL configuration (uncomment when PostgreSQL is available)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='intelipro_renewal'),
        'USER': config('DB_USER', default='intelipro_user'),
        'PASSWORD': config('DB_PASSWORD', default='SecurePassword123!'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 60,
        },
        # Connection pooling settings
        'CONN_MAX_AGE': 600,  # Keep connections alive for 10 minutes
        'CONN_HEALTH_CHECKS': True,  # Enable connection health checks
    }
}

# Cache Configuration (using dummy cache for development)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Redis Configuration (uncomment when Redis is available)
# REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': REDIS_URL,
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#             'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
#             'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
#         },
#         'KEY_PREFIX': 'intelipro_renewal',
#         'TIMEOUT': 300,
#     }
# }

# Channel Layers (WebSocket) - using in-memory for development
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Redis Channel Layers (uncomment when Redis is available)
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             'hosts': [REDIS_URL],
#             'capacity': 1500,
#             'expiry': 10,
#         },
#     },
# }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DATA_UPLOAD_MAX_MEMORY_SIZE = 26214400

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=config('JWT_REFRESH_TOKEN_LIFETIME', default=1440, cast=int)),
    'ROTATE_REFRESH_TOKEN': config('JWT_ROTATE_REFRESH_TOKEN', default=True, cast=bool),
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': config('JWT_ALGORITHM', default='HS256'),
    'SIGNING_KEY': config('JWT_SECRET_KEY', default=SECRET_KEY),
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://13.233.6.207:8000',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

# CSRF Configuration
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://13.233.6.207:8000',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=3600, cast=int)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Email Configuration
# EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
# EMAIL_HOST = config('EMAIL_HOST', default='localhost')
# EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
# EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
# EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
# EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
# DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@intelipro.com')
# ADMIN_EMAIL = config('ADMIN_EMAIL', default='admin@intelipro.com')

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=30, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='sahinayasin17@gmail.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='dfdr ihth gmbs ntxk')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='sahinayasin17@gmail.com')
ADMIN_EMAIL = config('ADMIN_EMAIL', default='sahinayasin17@gmail.com')

# File Storage Configuration
if config('AWS_ACCESS_KEY_ID', default=None):
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_DEFAULT_ACL = config('AWS_DEFAULT_ACL', default='private')
    AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default=None)
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    
    # Use S3 for media files
    # DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/'

# File Upload Settings
MAX_UPLOAD_SIZE = config('MAX_UPLOAD_SIZE', default=10485760, cast=int)  # 10MB
ALLOWED_FILE_TYPES = config('ALLOWED_FILE_TYPES', default='.xlsx,.csv,.pdf').split(',')
MAX_FILES_PER_UPLOAD = config('MAX_FILES_PER_UPLOAD', default=5, cast=int)

# # Celery Configuration
# CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/1')
# CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
# CELERY_ACCEPT_CONTENT = ['json']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_TIMEZONE = 'Asia/Kolkata'
# CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Third-party API Configuration
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')

WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_BUSINESS_ACCOUNT_ID = config('WHATSAPP_BUSINESS_ACCOUNT_ID', default='')

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# OPENAI_ORGANIZATION = config('OPENAI_ORGANIZATION', default='')
# OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-4')

OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
# OPENAI_ORGANIZATION = config('OPENAI_ORGANIZATION', default='')
OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-4')
OPENAI_MAX_TOKENS = config('OPENAI_MAX_TOKENS', default=150, cast=int)
OPENAI_TEMPERATURE = config('OPENAI_TEMPERATURE', default=0.3, cast=float)

RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')

# Bureau API Configuration (Customer Verification)
BUREAU_API_KEY = config('BUREAU_API_KEY', default='your_bureau_api_key_here')
BUREAU_BASE_URL = config('BUREAU_BASE_URL', default='https://api.sandbox.bureau.id/v2/services')

import platform
if platform.system() == 'Windows':
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Sahina1001\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    except ImportError:
        pass 

# Feature Flags
ENABLE_WHATSAPP_CAMPAIGNS = config('ENABLE_WHATSAPP_CAMPAIGNS', default=True, cast=bool)
ENABLE_SMS_CAMPAIGNS = config('ENABLE_SMS_CAMPAIGNS', default=True, cast=bool)
ENABLE_AI_ASSISTANT = config('ENABLE_AI_ASSISTANT', default=True, cast=bool)
ENABLE_ANALYTICS = config('ENABLE_ANALYTICS', default=True, cast=bool)
ENABLE_REAL_TIME_NOTIFICATIONS = config('ENABLE_REAL_TIME_NOTIFICATIONS', default=True, cast=bool)

# Campaign Settings
DEFAULT_CAMPAIGN_BATCH_SIZE = config('DEFAULT_CAMPAIGN_BATCH_SIZE', default=100, cast=int)
CAMPAIGN_PROCESSING_DELAY = config('CAMPAIGN_PROCESSING_DELAY', default=5, cast=int)
MAX_CAMPAIGN_RECIPIENTS = config('MAX_CAMPAIGN_RECIPIENTS', default=10000, cast=int)

# API Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'Intelipro Insurance Policy Renewal API',
    'DESCRIPTION': 'Comprehensive API for insurance policy renewal management system',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/',
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': config('LOG_FILE', default='logs/django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': config('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'renewal_backend': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}

AUTHENTICATION_BACKENDS = ['apps.users.backends.EmailBackend']

AUTH_USER_MODEL = 'users.User'

# Email tracking settings
BASE_URL = config('BASE_URL', default='http://13.233.6.207:8000')


CELERY_BEAT_SCHEDULE = {
    'send-scheduled-emails-every-minute': {
        'task': 'apps.email_manager.tasks.process_scheduled_emails',
        'schedule': crontab(minute='*'), 
    },
}
