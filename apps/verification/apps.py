from django.apps import AppConfig


class VerificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.verification'
    verbose_name = 'Customer Verification'
    
    def ready(self):
        """Import signal handlers when the app is ready."""
        pass
