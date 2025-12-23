from django.apps import AppConfig

class HierarchyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hierarchy'  # This MUST match your folder structure
    verbose_name = "Organization Hierarchy"