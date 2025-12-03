from django.apps import AppConfig


class EmailInboxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.email_inbox'

    def ready(self):
        import apps.email_inbox.signals
