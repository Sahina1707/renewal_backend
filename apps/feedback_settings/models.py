from django.db import models
from django.conf import settings
from apps.core.models import BaseModel 
class SurveySettings(BaseModel):
    """
    Global configuration for surveys per user/company.
    Controls notifications, automation, and general preferences.
    """
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='survey_settings'
    )

    LANGUAGE_CHOICES = [('en', 'English'),
        ('hi', 'Hindi'),
        ('te', 'Telugu'),
        ('ta', 'Tamil'),
        ('kn', 'Kannada'),
        ('bn', 'Bengali'),
        ('mr', 'Marathi'),
        ('gu', 'Gujarati'),
        ('ml', 'Malayalam'),
        ('ur', 'Urdu'),
        ('pa', 'Punjabi'),
        ('as', 'Assamese'),
        ('or','odia'),
        ('es', 'Español'),
        ('fr', 'Français'),]
    default_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    data_retention_period = models.IntegerField(default=12, help_text="Months to keep data")
    auto_archive_responses = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    weekly_reports = models.BooleanField(default=False)
    real_time_alerts = models.BooleanField(default=True)
    negative_feedback_threshold = models.IntegerField(default=3)
    auto_send_post_purchase = models.BooleanField(default=False)
    follow_up_reminders = models.BooleanField(default=True)
    smart_response_routing = models.BooleanField(default=False)
    class Meta:
        db_table='feedback_settings'
    def __str__(self):
        return f"Settings: {self.owner}"


class IntegrationCredential(BaseModel):
    """
    Stores API keys and webhooks for external tools.
    Separated from settings for security and flexibility.
    """
    PROVIDER_CHOICES = [
        ('slack', 'Slack'),
        ('hubspot', 'HubSpot'),
        ('salesforce', 'Salesforce'),
        ('zapier', 'Zapier'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='integrations'
    )
    
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    is_active = models.BooleanField(default=False)
    api_key = models.CharField(max_length=500, blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    meta_data = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('owner', 'provider')
        db_table='feedback_settings_integration_credentials'

    def __str__(self):
        return f"{self.provider} ({self.owner})"