from django.apps import AppConfig

class FeedbackSettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.feedback_settings'

    def ready(self):
        import apps.feedback_settings.signals