from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import json

User = get_user_model()
def today_date():
    return timezone.now().date()

class WhatsAppProvider(models.Model):
    PROVIDER_CHOICES = [
        ('meta', 'Meta Business API'),
        ('twilio', 'Twilio WhatsApp'),
        ('gupshup', 'Gupshup WhatsApp'),
        ('360dialog', '360Dialog'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'), 
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('suspended', 'Suspended'),
        ('disabled', 'Disabled'),
    ]
    
    QUALITY_RATING_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Friendly name for this provider")
    
    provider_type = models.CharField(
        max_length=20, 
        choices=PROVIDER_CHOICES, 
        default='meta'
    )
    access_token = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        help_text="The secret key/token (Encrypted)"
    )
    
    account_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="The account identifier"
    )
    
    phone_number_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="The identifier for the phone number"
    )
    
    # Maps to: App Name (Gupshup)
    app_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="App ID or App Name"
    )

    api_url = models.CharField( 
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="API Endpoint URL"
    )
    
    api_version = models.CharField(max_length=10, default="v18.0", blank=True, null=True)
    business_name = models.CharField(max_length=255, blank=True, null=True)
    business_description = models.TextField(blank=True, null=True)
    business_email = models.EmailField(blank=True, null=True)
    business_vertical = models.CharField(max_length=100, blank=True, null=True)
    business_address = models.TextField(blank=True, null=True)
    
    enable_auto_reply = models.BooleanField(default=True, help_text="Enable automatic replies")
    use_knowledge_base = models.BooleanField(default=True, help_text="Use RAG knowledge base for responses")
    greeting_message = models.TextField(
        default="Hello! I'm your AI assistant. How can I help you today?",
        help_text="Welcome message for new conversations"
    )
    fallback_message = models.TextField(
        default="I'm sorry, I didn't understand that. Could you please rephrase your question?",
        help_text="Message when AI can't understand the query"
    )
    enable_business_hours = models.BooleanField(default=False, help_text="Restrict responses to business hours")
    business_hours_start = models.TimeField(default="09:00:00", help_text="Business hours start time")
    business_hours_end = models.TimeField(default="17:00:00", help_text="Business hours end time")
    business_timezone = models.CharField(max_length=50, default="UTC", help_text="Business timezone")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    quality_rating = models.CharField(max_length=10, choices=QUALITY_RATING_CHOICES, default='unknown')
    last_health_check = models.DateTimeField(blank=True, null=True)
    health_status = models.CharField(max_length=20, default='unknown', choices=[
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
        ('unknown', 'Unknown'),
    ])
    
    daily_limit = models.PositiveIntegerField(default=1000, help_text="Daily message limit")
    monthly_limit = models.PositiveIntegerField(default=30000, help_text="Monthly message limit")
    rate_limit_per_minute = models.PositiveIntegerField(default=10, help_text="Rate limit per minute")
    messages_sent_today = models.PositiveIntegerField(default=0)
    messages_sent_this_month = models.PositiveIntegerField(default=0)
    last_reset_daily = models.DateField(default=today_date)
    last_reset_monthly = models.DateField(default=today_date)


    
    is_default = models.BooleanField(default=False, help_text="Use this provider by default")
    is_active = models.BooleanField(default=True, help_text="Activate this provider")
    
    webhook_verify_token = models.CharField(
        max_length=255, 
        help_text="A unique token to verify incoming webhooks",
        blank=True,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_whatsapp_provider')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_whatsapp_provider')
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'whatsapp_provider' 
        ordering = ['-is_default', 'name']
        verbose_name = 'WhatsApp Provider'
        verbose_name_plural = 'WhatsApp Providers'
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"
    
    def can_send_message(self) -> bool:
        if not self.is_active or self.status not in ['verified', 'connected']:
            return False
        
        if self.messages_sent_today >= self.daily_limit:
            return False
        
        if self.messages_sent_this_month >= self.monthly_limit:
            return False
        
        return True
    
    def get_primary_phone_number(self):
        return self.phone_numbers.filter(is_primary=True, is_active=True).first()
    
    def get_active_phone_numbers(self):
        return self.phone_numbers.filter(is_active=True, status='verified')


class WhatsAppPhoneNumber(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
        ('suspended', 'Suspended'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='phone_numbers',
        null=True,
        blank=True
    )
    
    phone_number_id = models.CharField(max_length=50, help_text="Phone Number ID from Meta")
    phone_number = models.CharField(max_length=20, help_text="Phone number with country code")
    display_phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Formatted display number")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_primary = models.BooleanField(default=False, help_text="Primary phone number for this WABA")
    is_active = models.BooleanField(default=True)
    
    quality_rating = models.CharField(max_length=10, choices=[
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('unknown', 'Unknown'),
    ], default='unknown')
    
    messages_sent_today = models.PositiveIntegerField(default=0)
    messages_sent_this_month = models.PositiveIntegerField(default=0)
    last_message_sent = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'whatsapp_phone_numbers'
        unique_together = ['provider', 'phone_number_id'] 
        ordering = ['-is_primary', '-created_at']
        verbose_name = 'WhatsApp Phone Number'
        verbose_name_plural = 'WhatsApp Phone Numbers'
    
    def __str__(self):
        return f"{self.display_phone_number or self.phone_number} ({self.provider.name})"


class WhatsAppMessageTemplate(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disabled', 'Disabled'),
    ]
    
    CATEGORY_CHOICES = [
        ('AUTHENTICATION', 'Authentication'),
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utility'),
        ('OTP', 'One-Time Password'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en_US', 'English (US)'),
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('pt', 'Portuguese'),
        ('ar', 'Arabic'),
        ('zh', 'Chinese'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='message_templates',
        null=True,
        blank=True
    )
    
    name = models.CharField(max_length=100, help_text="Template name")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    
    header_text = models.TextField(blank=True, null=True, help_text="Header text (optional)")
    body_text = models.TextField(help_text="Main message body")
    footer_text = models.TextField(blank=True, null=True, help_text="Footer text (optional)")
    
    components = models.JSONField(default=list, help_text="Template components (buttons, media, etc.)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    meta_template_id = models.CharField(max_length=100, blank=True, null=True, help_text="Template ID from Meta")
    rejection_reason = models.TextField(blank=True, null=True, help_text="Reason for rejection if applicable")
    
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'whatsapp_message_templates'
        unique_together = ['provider', 'name', 'language']
        ordering = ['-created_at']
        verbose_name = 'WhatsApp Message Template'
        verbose_name_plural = 'WhatsApp Message Templates'
    
    def __str__(self):
        return f"{self.name} ({self.provider.name}) - {self.get_language_display()}"
    
    def is_approved(self) -> bool:
        return self.status == 'approved' and self.meta_template_id


class WhatsAppMessage(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('template', 'Template Message'),
        ('interactive', 'Interactive Message'),
        ('media', 'Media Message'),
        ('location', 'Location Message'),
        ('contact', 'Contact Message'),
    ]
    
    DIRECTION_CHOICES = [
        ('outbound', 'Outbound'),
        ('inbound', 'Inbound'),
    ]
    
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='messages',
        null=True,
        blank=True
    )
    phone_number = models.ForeignKey(
        WhatsAppPhoneNumber, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='messages'
    )
    
    message_id = models.CharField(max_length=100, unique=True, help_text="WhatsApp message ID")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    
    to_phone_number = models.CharField(max_length=20, help_text="Recipient phone number")
    from_phone_number = models.CharField(max_length=20, help_text="Sender phone number")
    
    content = models.JSONField(default=dict, help_text="Message content (text, media, etc.)")
    template = models.ForeignKey(
        WhatsAppMessageTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='messages'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    error_code = models.CharField(max_length=50, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    
    campaign = models.ForeignKey(
        'campaigns.Campaign', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='whatsapp_messages'
    )
    customer = models.ForeignKey(
        'customers.Customer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='whatsapp_messages'
    )
    
    metadata = models.JSONField(default=dict, help_text="Additional message metadata")
    
    class Meta:
        db_table = 'whatsapp_messages'
        ordering = ['-created_at']
        verbose_name = 'WhatsApp Message'
        verbose_name_plural = 'WhatsApp Messages'
    
    def __str__(self):
        return f"{self.get_direction_display()} {self.get_message_type_display()} - {self.to_phone_number}"


class WhatsAppWebhookEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('message', 'Message Received'),
        ('message_status', 'Message Status Update'),
        ('account_update', 'Account Update'),
        ('phone_number_update', 'Phone Number Update'),
        ('template_status', 'Template Status Update'),
        ('message_template_status_update', 'Template Status Update'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='received_webhook_events',
        null=True, 
        blank=True
    )
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    raw_data = models.JSONField(default=dict, help_text="Raw webhook payload")
    
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True, null=True)
    
    message = models.ForeignKey(
        WhatsAppMessage, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='webhook_events'
    )
    
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'whatsapp_webhook_events'
        ordering = ['-received_at']
        verbose_name = 'WhatsApp Webhook Event'
        verbose_name_plural = 'WhatsApp Webhook Events'
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.received_at}"


class WhatsAppFlow(models.Model):
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='flows',
        null=True,
        blank=True
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    flow_json = models.JSONField(help_text="Flow definition in JSON format")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_active = models.BooleanField(default=True)
    
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'whatsapp_flows'
        ordering = ['-created_at']
        verbose_name = 'WhatsApp Flow'
        verbose_name_plural = 'WhatsApp Flows'
    
    def __str__(self):
        return f"{self.name} ({self.provider.name})"


class WhatsAppAccountHealthLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='health_logs',
        null=True,
        blank=True
    )
    
    health_status = models.CharField(max_length=20, choices=[
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
        ('warning', 'Warning'),
    ])
    check_details = models.JSONField(default=dict, help_text="Detailed health check results")
    error_message = models.TextField(blank=True, null=True)
    
    checked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_account_health_logs'
        ordering = ['-checked_at']
        verbose_name = 'WhatsApp Account Health Log'
        verbose_name_plural = 'WhatsApp Account Health Logs'
    
    def __str__(self):
        return f"{self.provider.name} - {self.health_status} ({self.checked_at})"


class WhatsAppAccountUsageLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    provider = models.ForeignKey(
        WhatsAppProvider, 
        on_delete=models.CASCADE, 
        related_name='usage_logs',
        null=True,
        blank=True
    )
    
    messages_sent = models.PositiveIntegerField(default=0)
    messages_delivered = models.PositiveIntegerField(default=0)
    messages_failed = models.PositiveIntegerField(default=0)
    messages_read = models.PositiveIntegerField(default=0)
    date = models.DateField(default=today_date)

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_account_usage_logs'
        unique_together = ['provider', 'date'] 
        ordering = ['-date']
        verbose_name = 'WhatsApp Account Usage Log'
        verbose_name_plural = 'WhatsApp Account Usage Logs'
    
    def __str__(self):
        return f"{self.provider.name} - {self.date} ({self.messages_sent} sent)"