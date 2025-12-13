from django.apps import AppConfig
class WhatsappProviderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.whatsapp_provider'
    label = 'whatsapp_provider'  
    verbose_name = 'WhatsApp Business Provider'
    
    def ready(self):
        try:
            import apps.whatsapp_provider.signals
        except ImportError:
            pass
