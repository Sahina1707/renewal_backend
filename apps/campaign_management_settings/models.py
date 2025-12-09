from django.db import models
from django.conf import settings

class CampaignSetting(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campaign_settings')

    email_provider = models.ForeignKey(
        'email_provider.EmailProviderConfig', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='campaign_settings_email'
    )
    sms_provider = models.ForeignKey(
        'sms_provider.SmsProvider', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='campaign_settings_sms'
    )

    whatsapp_provider = models.ForeignKey(
        'whatsapp_provider.WhatsAppProvider', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='campaign_settings_whatsapp'
    )
    consent_required = models.BooleanField(default=True, help_text="Require explicit consent before sending")
    dnd_compliance = models.BooleanField(default=True, help_text="Check Do Not Disturb registry")
    opt_in_required = models.BooleanField(default=True, help_text="Require users to opt-in for marketing")
    data_retention_days = models.IntegerField(default=365, help_text="Days to retain campaign data")

    email_rate_limit = models.IntegerField(default=1000, help_text="Emails per hour")
    sms_rate_limit = models.IntegerField(default=100, help_text="SMS per hour")
    whatsapp_rate_limit = models.IntegerField(default=80, help_text="WhatsApp messages per hour")
    
    batch_size = models.IntegerField(default=50, help_text="Messages per batch")
    retry_attempts = models.IntegerField(default=3, help_text="Failed message retry attempts")
    template_approval_required = models.BooleanField(default=True, help_text="Require admin approval for new templates")
    dlt_template_required = models.BooleanField(default=True, help_text="Require DLT template ID for SMS")
    auto_save_templates = models.BooleanField(default=True, help_text="Automatically save drafts")
    tracking_enabled = models.BooleanField(default=True, help_text="Enable open, click, and delivery tracking")
    webhook_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to receive events")  
    REPORTING_INTERVAL_CHOICES = [
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]
    reporting_interval = models.CharField(
        max_length=20, 
        choices=REPORTING_INTERVAL_CHOICES, 
        default='daily'
    )
    EXPORT_FORMAT_CHOICES = [
        ('CSV', 'CSV'),
        ('XLSX', 'Excel (XLSX)'),
        ('PDF', 'PDF Report'),
        ('JSON', 'JSON'),
    ]
    export_format = models.CharField(
        max_length=10,
        choices=EXPORT_FORMAT_CHOICES,
        default='CSV',
        help_text="Preferred format for downloadable reports"
    )
    class Meta:
        db_table = 'campaign_settings'  
        verbose_name = "Campaign Setting"
        verbose_name_plural = "Campaign Settings"

    def __str__(self):
        return f"Full Settings for {self.user.username}"