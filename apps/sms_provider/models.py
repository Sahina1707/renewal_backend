from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class SmsProvider(models.Model):
    """
    Stores configuration for various SMS providers.
    """
    PROVIDER_CHOICES = [
        ('twilio', 'Twilio SMS'),
        ('msg91', 'MSG91'),
        ('aws_sns', 'AWS SNS'),
        ('textlocal', 'TextLocal'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('suspended', 'Suspended'),
    ]

    name = models.CharField(max_length=100, help_text="A friendly name for this provider")
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    credentials = models.JSONField(default=dict, help_text="Encrypted API credentials for the provider")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_default = models.BooleanField(default=False, help_text="Use this provider by default for SMS")
    is_active = models.BooleanField(default=True, help_text="Activate this provider")

    # Usage and Rate Limiting
    rate_limit_per_minute = models.PositiveIntegerField(default=10, help_text="Max messages per minute")
    daily_limit = models.PositiveIntegerField(default=1000)
    monthly_limit = models.PositiveIntegerField(default=10000)
    messages_sent_today = models.PositiveIntegerField(default=0)
    messages_sent_total = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_sms_providers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_sms_providers')
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'sms_provider_type' 
        ordering = ['-is_default', 'name']
        verbose_name = "SMS Provider"
        verbose_name_plural = "SMS Providers"

    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"

    def save(self, *args, **kwargs):
        if self.is_default:
            SmsProvider.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class SmsMessage(models.Model):
    """
    Logs individual SMS messages sent through the providers.
    """
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('undelivered', 'Undelivered'),
    ]

    provider = models.ForeignKey(SmsProvider, on_delete=models.CASCADE, related_name='sms_messages')
    message_sid = models.CharField(max_length=255, unique=True, help_text="Provider's unique message ID")

    to_phone_number = models.CharField(max_length=20, help_text="Recipient phone number")
    from_number = models.CharField(max_length=20, help_text="Sender number or ID")
    content = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    error_code = models.CharField(max_length=50, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Context
    campaign = models.ForeignKey(
        'campaign_manager.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_messages'
    )
    contact = models.ForeignKey(
        'audience_manager.AudienceContact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_messages'
    )

    class Meta:
        db_table = 'sms_provider_message' 
        ordering = ['-created_at']
        verbose_name = "SMS Message"
        verbose_name_plural = "SMS Messages"

    def __str__(self):
        return f"SMS to {self.to_phone_number} via {self.provider.name} ({self.status})"