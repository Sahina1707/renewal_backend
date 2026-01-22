from django.apps import AppConfig

class FeedbackConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.feedback_and_surveys'

    def ready(self):
        import apps.feedback_and_surveys.signals