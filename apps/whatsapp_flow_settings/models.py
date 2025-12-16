from django.db import models
from django.db.models import Manager
from django.conf import settings
from django.core.exceptions import ValidationError
from openai import max_retries
from django.db.models import Manager,UniqueConstraint, Q
import pytz

# --- 1. WhatsApp Configuration (Main Settings) ---
# (This remains largely the same, but we add the AuditLog model below)
class WhatsAppConfiguration(models.Model):
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


# --- 2. Dynamic Access Roles (New Model) ---
class FlowAccessRole(models.Model):
    """
    Stores roles dynamically (Admin, Editor, Viewer, etc.)
    You can add/remove these without code changes.
    """
    name = models.CharField(max_length=50, unique=True, help_text="e.g., 'Admin', 'Viewer'")
    description = models.TextField(blank=True, help_text="Detailed description of what this role can do.")
    
    # We can add boolean flags here to define permissions granularly later
    can_publish = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)

    def __str__(self):
        return self.name

# --- Soft Delete Logic ---
class NonDeletedManager(Manager):
    def get_queryset(self):
        # This is the core logic: exclude records where is_deleted is True
        return super().get_queryset().filter(is_deleted=False)

class SoftDeleteBase(models.Model):
    is_deleted = models.BooleanField(default=False)

    # Use the custom manager as the default 'objects' manager
    objects = NonDeletedManager() 
    # Keep a manager that returns EVERYTHING (for audit/admin view)
    all_objects = models.Manager() 

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        # Override the delete method to perform a soft delete
        self.is_deleted = True
        self.save()
        
class WhatsAppAccessPermission(SoftDeleteBase):
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