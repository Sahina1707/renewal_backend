from django.apps import AppConfig


class PoliciesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.policies'
    verbose_name = 'Policy Management'

    def ready(self):
        import apps.policies.signals