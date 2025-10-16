from django.apps import AppConfig


class UploadChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.upload_chatbot'
    verbose_name = 'Upload Chatbot'
    
    def ready(self):
        """Import signals when the app is ready"""
        try:
            import apps.upload_chatbot.signals
        except ImportError:
            pass
