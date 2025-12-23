from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError


class SocialIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.social_integration"

    def ready(self):
        """
        Auto-create default social platforms.
        Safe-guarded to avoid issues during migrations.
        """
        try:
            from .models import SocialPlatform

            platforms = [
                ("facebook", "Facebook"),
                ("twitter", "Twitter"),
                ("instagram", "Instagram"),
                ("linkedin", "LinkedIn"),
                ("wechat", "WeChat"),
                ("line", "LINE"),
                ("telegram", "Telegram"),
            ]

            for key, name in platforms:
                SocialPlatform.objects.get_or_create(
                    platform=key,
                    defaults={"display_name": name}
                )

        except (OperationalError, ProgrammingError):
            # Database not ready (migrate / makemigrations)
            pass
