from django.contrib import admin
from .models import SurveySettings, IntegrationCredential

@admin.register(SurveySettings)
class SurveySettingsAdmin(admin.ModelAdmin):
    list_display = ('owner', 'default_language', 'email_notifications', 'negative_feedback_threshold')
    search_fields = ('owner__email', 'owner__username')
    list_filter = ('default_language', 'email_notifications')

@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ('owner', 'provider', 'is_active', 'updated_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('owner__email', 'api_key')