from django.apps import AppConfig


class SmsProviderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sms_provider'
    verbose_name = "SMS Provider"
