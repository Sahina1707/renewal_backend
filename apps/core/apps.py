from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core Utilities'
    
    def ready(self):
        """Initialize app when Django starts"""
        # Import signal handlers
        try:
            import apps.core.signals  # noqa
        except ImportError:
            pass 