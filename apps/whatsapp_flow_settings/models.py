from django.db import models
from django.db.models import Manager
from django.conf import settings
from django.core.exceptions import ValidationError
from openai import max_retries
from django.db.models import Manager,UniqueConstraint, Q
import pytz

class AuditLogModel(models.Model):
    """
    Abstract base class that provides self-updating
    'created' and 'modified' fields, plus user tracking.
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Updated")
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        verbose_name="Created By"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        verbose_name="Updated By"
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        abstract = True

class WhatsAppConfiguration(AuditLogModel):
    # API Credentials
    phone_number_id = models.CharField(max_length=255, help_text="Meta Phone Number ID")
    access_token = models.TextField(help_text="Meta Access Token")
    webhook_url = models.URLField(help_text="Your public webhook URL")
    verify_token = models.CharField(max_length=255, help_text="Webhook Verify Token")
    is_enabled = models.BooleanField(default=True, verbose_name="Enable WhatsApp Business API")

    # Business Hours
    enable_business_hours = models.BooleanField(default=True)
    business_start_time = models.TimeField(default="09:00", help_text="Opening time")
    business_end_time = models.TimeField(default="18:00", help_text="Closing time")
    TIMEZONE_CHOICES = tuple(zip(pytz.all_timezones, pytz.all_timezones))
    timezone = models.CharField(max_length=32, choices=TIMEZONE_CHOICES, default='Asia/Kolkata')

    # Message Settings & 
    fallback_message = models.TextField(default="Thank you for your message. We will get back to you soon.")
    max_retries = models.PositiveSmallIntegerField(default=3, help_text="Maximum retry attempts for failed flows") 
    retry_delay = models.PositiveSmallIntegerField(default=300, help_text="Delay between retry attempts in seconds") 
    # Rate Limiting
    enable_rate_limiting = models.BooleanField(default=True)
    messages_per_minute = models.PositiveIntegerField(default=60)
    messages_per_hour = models.PositiveIntegerField(default=1000)
    
    # Flow Builder Settings
    enable_visual_flow_builder = models.BooleanField(default=True)
    enable_message_templates = models.BooleanField(default=True)
    enable_auto_response = models.BooleanField(default=True)
    enable_analytics_and_reports = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.pk and WhatsAppConfiguration.objects.exists():
            raise ValidationError('There can be only one WhatsApp Configuration instance')
        return super(WhatsAppConfiguration, self).save(*args, **kwargs)

    def __str__(self):
        return "WhatsApp Global Settings"

class FlowAccessRole(AuditLogModel):
    """
    Stores roles dynamically (Admin, Editor, Viewer, etc.)
    You can add/remove these without code changes.
    """
    name = models.CharField(max_length=50, unique=True, help_text="e.g., 'Admin', 'Viewer'")
    description = models.TextField(blank=True, help_text="Detailed description of what this role can do.")    
    can_publish = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class NonDeletedManager(Manager):
    def get_queryset(self):
        # This is the core logic: exclude records where is_deleted is True
        return super().get_queryset().filter(is_deleted=False)

class SoftDeleteBase(models.Model):
    is_deleted = models.BooleanField(default=False)
    objects = NonDeletedManager() 
    all_objects = models.Manager() 

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()
        
class WhatsAppAccessPermission(SoftDeleteBase,AuditLogModel):
    """
    Assigns a dynamic role to a specific user.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="whatsapp_flow_permission",
    ) 
    
    role = models.ForeignKey(FlowAccessRole, on_delete=models.PROTECT) 

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['user'], 
                condition=Q(is_deleted=False), 
                name='unique_active_permission'
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

class FlowAuditLog(models.Model):
    ACTION_CHOICES = [
        ('PUBLISH', 'Flow Published'),
        ('EDIT', 'Flow Edited'),
        ('ERROR', 'System Error'),
        ('USER_CHANGE', 'User Permission Change'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="flow_actions")
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.TextField(help_text="Details of the action, e.g., Flow ID, message content.")
    
    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.get_action_type_display()}"