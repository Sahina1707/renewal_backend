from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel, TimestampedModel
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.templates.models import Template
from apps.files_upload.models import FileUpload
from apps.target_audience.models import TargetAudience
from apps.email_provider.models import EmailProviderConfig
from django.utils import timezone
try:
    from apps.sms_provider.models import SmsProvider
except ImportError:
    SmsProvider = None

try:
    from apps.whatsapp_provider.models import WhatsAppProvider
except ImportError:
    WhatsAppProvider = None

from decimal import Decimal
import uuid
import json
from datetime import timedelta

User = get_user_model()
class CampaignType(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    default_channels = models.JSONField(default=list, help_text="Default communication channels for this campaign type")
    class Meta:
        db_table = 'campaign_types'
        ordering = ['name']
    
    def __str__(self):
        return self.name
class Campaign(BaseModel):
    CAMPAIGN_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    SIMPLIFIED_STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
    ]
    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('push', 'Push Notification'),
    ]
    
    name = models.CharField(max_length=200)
    campaign_type = models.ForeignKey(CampaignType, on_delete=models.CASCADE, related_name='campaigns')
    template = models.ForeignKey(Template, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS_CHOICES, default='active')
    upload = models.ForeignKey(FileUpload,on_delete=models.SET_NULL,null=True,blank=True,related_name='campaigns')
    channels = models.JSONField(default=list, help_text="List of communication channels")
    target_audience = models.ForeignKey(TargetAudience,on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns'
    )
    email_provider = models.ForeignKey(
        EmailProviderConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_campaigns',
        help_text="Specific provider for Email channel. If null, uses system default."
    )

    if SmsProvider:
        sms_provider = models.ForeignKey(
            SmsProvider,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name='sms_campaigns',
            help_text="Specific provider for SMS channel. If null, uses system default."
        )

    if WhatsAppProvider:
        whatsapp_provider = models.ForeignKey(
            WhatsAppProvider,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name='whatsapp_campaigns',
            help_text="Specific provider for WhatsApp channel. If null, uses system default."
        )

    schedule_type = models.CharField(max_length=20, choices=[
        ('immediate', 'Immediate'),
        ('schedule later', 'Scheduled Later'),
    ], default='immediate')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(default=dict, blank=True)
    
    enable_advanced_scheduling = models.BooleanField(
        default=False,
        help_text="Enable multi-channel communication intervals"
    )
    advanced_scheduling_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration for advanced scheduling intervals"
    )
    
    subject_line = models.CharField(max_length=200, blank=True)
    
    use_personalization = models.BooleanField(default=True)
    personalization_fields = models.JSONField(default=list, blank=True)
    
    target_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    opened_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)
    total_responses = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_campaigns')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_campaigns')
    
    class Meta:
        db_table = 'campaigns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['campaign_type', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def get_simplified_status(self):
        if self.status in ['active', 'scheduled']:
            return 'active'
        elif self.status == 'paused':
            return 'paused'
        elif self.status in ['completed', 'cancelled']:
            return 'paused'  
        else:  
            return 'paused'

    def set_simplified_status(self, simplified_status):
        if simplified_status == 'active':
            if self.status == 'paused':
                self.status = 'active'
            elif self.status == 'draft':
                self.status = 'active'
        elif simplified_status == 'paused':
            if self.status in ['active', 'scheduled']:
                self.status = 'paused'
        self.save(update_fields=['status'])

    def update_campaign_statistics(self):
        recipients = self.recipients.all()

        self.sent_count = recipients.filter(
            email_status__in=['sent', 'delivered']
        ).count()

        self.delivered_count = recipients.filter(
            Q(email_status='delivered') |
            Q(email_delivered_at__isnull=False)
        ).count()

        self.opened_count = recipients.filter(
            email_engagement__in=['opened', 'clicked', 'replied', 'forwarded']
        ).count()

        self.clicked_count = recipients.filter(
            email_engagement__in=['clicked', 'replied', 'forwarded']
        ).count()

        self.total_responses = recipients.filter(
            email_engagement__in=['replied', 'forwarded']
        ).count()

        self.save(update_fields=[
            'sent_count', 'delivered_count', 'opened_count',
            'clicked_count', 'total_responses'
        ])

    def get_campaign_metrics(self):
        """Get comprehensive campaign metrics"""
        recipients = self.recipients.all()
        total_recipients = recipients.count()

        if total_recipients == 0:
            return {
                'total_recipients': 0,
                'sent_rate': 0,
                'delivery_rate': 0,
                'open_rate': 0,
                'click_rate': 0,
                'response_rate': 0
            }

        return {
            'total_recipients': total_recipients,
            'sent_count': self.sent_count,
            'delivered_count': self.delivered_count,
            'opened_count': self.opened_count,
            'clicked_count': self.clicked_count,
            'total_responses': self.total_responses,
            'sent_rate': round((self.sent_count / total_recipients) * 100, 2),
            'delivery_rate': round((self.delivered_count / self.sent_count) * 100, 2) if self.sent_count > 0 else 0,
            'open_rate': round((self.opened_count / self.delivered_count) * 100, 2) if self.delivered_count > 0 else 0,
            'click_rate': round((self.clicked_count / self.opened_count) * 100, 2) if self.opened_count > 0 else 0,
            'response_rate': round((self.total_responses / total_recipients) * 100, 2)
        }
    
    @property
    def delivery_rate(self):
        """Calculate delivery rate percentage"""
        if self.sent_count == 0:
            return 0
        return round((self.delivered_count / self.sent_count) * 100, 2)
    
    @property
    def open_rate(self):
        """Calculate open rate percentage"""
        if self.delivered_count == 0:
            return 0
        return round((self.opened_count / self.delivered_count) * 100, 2)
    
    @property
    def click_rate(self):
        """Calculate click rate percentage"""
        if self.opened_count == 0:
            return 0
        return round((self.clicked_count / self.opened_count) * 100, 2)
    
    @property
    def response_rate(self):
        """Calculate response rate percentage"""
        if self.delivered_count == 0:
            return 0
        return round((self.total_responses / self.delivered_count) * 100, 2)

class CampaignSegment(BaseModel):
    """Customer segments for targeted campaigns"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    criteria = models.JSONField(default=dict, help_text="Segmentation criteria in JSON format")
    
    customer_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'campaign_segments'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.customer_count} customers)"

class CampaignRecipient(BaseModel):
    """Individual recipients of a campaign with enhanced tracking"""
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('rejected', 'Rejected'),
        ('opted_out', 'Opted Out'),
        ('blocked', 'Blocked'),
    ]

    ENGAGEMENT_STATUS_CHOICES = [
        ('not_opened', 'Not Opened'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('replied', 'Replied'),
        ('forwarded', 'Forwarded'),
        ('unsubscribed', 'Unsubscribed'),
    ]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='recipients')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='campaign_recipients')
    policy = models.ForeignKey(Policy, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaign_recipients')

    email_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')
    whatsapp_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')
    sms_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')

    email_engagement = models.CharField(max_length=20, choices=ENGAGEMENT_STATUS_CHOICES, default='not_opened')
    whatsapp_engagement = models.CharField(max_length=20, choices=ENGAGEMENT_STATUS_CHOICES, default='not_opened')
    sms_engagement = models.CharField(max_length=20, choices=ENGAGEMENT_STATUS_CHOICES, default='not_opened')

    tracking_id = models.CharField(max_length=64, unique=True, blank=True)
    
    provider_message_id = models.CharField(max_length=255, blank=True, null=True, help_text="Message ID from email provider (SendGrid, SES, etc.)")

    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_delivered_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_delivered_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    sms_delivered_at = models.DateTimeField(null=True, blank=True)

    email_opened_at = models.DateTimeField(null=True, blank=True)
    email_clicked_at = models.DateTimeField(null=True, blank=True)
    email_replied_at = models.DateTimeField(null=True, blank=True)
    whatsapp_read_at = models.DateTimeField(null=True, blank=True)
    whatsapp_replied_at = models.DateTimeField(null=True, blank=True)
    sms_replied_at = models.DateTimeField(null=True, blank=True)

    email_error_message = models.TextField(blank=True)
    whatsapp_error_message = models.TextField(blank=True)
    sms_error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)

    email_content = models.JSONField(default=dict, blank=True, help_text="Personalized email content")
    whatsapp_content = models.JSONField(default=dict, blank=True, help_text="Personalized WhatsApp content")
    sms_content = models.JSONField(default=dict, blank=True, help_text="Personalized SMS content")

    has_responded = models.BooleanField(default=False)
    response_channel = models.CharField(max_length=20, choices=Campaign.CHANNEL_CHOICES, blank=True)
    response_type = models.CharField(max_length=30, choices=[
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('callback_requested', 'Callback Requested'),
        ('more_info_requested', 'More Info Requested'),
        ('complaint', 'Complaint'),
        ('unsubscribe', 'Unsubscribe'),
        ('policy_renewed', 'Policy Renewed'),
        ('payment_made', 'Payment Made'),
        ('document_requested', 'Document Requested'),
    ], blank=True)
    response_notes = models.TextField(blank=True)
    response_received_at = models.DateTimeField(null=True, blank=True)

    conversion_achieved = models.BooleanField(default=False, help_text="Did this recipient convert (renew/purchase)?")
    conversion_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Value of conversion")
    conversion_date = models.DateTimeField(null=True, blank=True)

    recipient_metadata = models.JSONField(default=dict, blank=True, help_text="Additional recipient-specific data")
    class Meta:
        db_table = 'campaign_recipients'
        unique_together = ['campaign', 'customer']
        indexes = [
            models.Index(fields=['campaign', 'email_status']),
            models.Index(fields=['campaign', 'whatsapp_status']),
            models.Index(fields=['campaign', 'sms_status']),
            models.Index(fields=['campaign', 'has_responded']),
            models.Index(fields=['campaign', 'conversion_achieved']),
            models.Index(fields=['email_status', 'email_sent_at']),
            models.Index(fields=['customer', 'campaign']),
            models.Index(fields=['response_type', 'response_received_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.campaign.name} - {self.customer.full_name}"

    def save(self, *args, **kwargs):
        """Generate tracking ID if not exists"""
        if not self.tracking_id:
            import uuid
            import hashlib
            unique_string = f"{self.campaign_id}-{self.customer_id}-{uuid.uuid4()}"
            self.tracking_id = hashlib.sha256(unique_string.encode()).hexdigest()[:32]
        super().save(*args, **kwargs)

    @property
    def primary_status(self):
        if 'email' in self.campaign.channels:
            return self.email_status
        elif 'whatsapp' in self.campaign.channels:
            return self.whatsapp_status
        elif 'sms' in self.campaign.channels:
            return self.sms_status
        return 'pending'

    @property
    def is_delivered(self):
        return (self.email_status == 'delivered' or
                self.whatsapp_status == 'delivered' or
                self.sms_status == 'delivered')

    @property
    def is_engaged(self):
        return (self.email_engagement in ['opened', 'clicked', 'replied'] or
                self.whatsapp_engagement in ['opened', 'clicked', 'replied'] or
                self.sms_engagement in ['opened', 'clicked', 'replied'])

    def mark_sent(self, channel, timestamp=None):
        from django.utils import timezone
        if timestamp is None:
            timestamp = timezone.now()

        if channel == 'email':
            self.email_status = 'sent'
            self.email_sent_at = timestamp
        elif channel == 'whatsapp':
            self.whatsapp_status = 'sent'
            self.whatsapp_sent_at = timestamp
        elif channel == 'sms':
            self.sms_status = 'sent'
            self.sms_sent_at = timestamp
        self.save()

    def mark_delivered(self, channel, timestamp=None):
        if timestamp is None:
            timestamp = timezone.now()

        if channel == 'email':
            self.email_status = 'delivered'
            self.email_delivered_at = timestamp
        elif channel == 'whatsapp':
            self.whatsapp_status = 'delivered'
            self.whatsapp_delivered_at = timestamp
        elif channel == 'sms':
            self.sms_status = 'delivered'
            self.sms_delivered_at = timestamp
        self.save()

    def mark_opened(self, channel, timestamp=None):
        if timestamp is None:
            timestamp = timezone.now()

        if channel == 'email':
            self.email_engagement = 'opened'
            self.email_opened_at = timestamp
        elif channel == 'whatsapp':
            self.whatsapp_engagement = 'opened'
            self.whatsapp_read_at = timestamp
        self.save()

    def mark_failed(self, channel, error_message="", timestamp=None):
        """Mark message as failed for specific channel"""
        from django.utils import timezone
        if timestamp is None:
            timestamp = timezone.now()

        if channel == 'email':
            self.email_status = 'failed'
            self.email_error_message = error_message
        elif channel == 'whatsapp':
            self.whatsapp_status = 'failed'
            self.whatsapp_error_message = error_message
        elif channel == 'sms':
            self.sms_status = 'failed'
            self.sms_error_message = error_message

        self.retry_count += 1
        self.save()

class CampaignTemplate(BaseModel):
    """Reusable campaign templates"""
    TEMPLATE_TYPE_CHOICES = [
        ('email', 'Email Template'),
        ('whatsapp', 'WhatsApp Template'),
        ('sms', 'SMS Template'),
    ]
    
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    
    variables = models.JSONField(default=list, help_text="List of template variables")
    
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'campaign_templates'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"
class CampaignSchedule(BaseModel):
    """Scheduled campaign executions"""
    SCHEDULE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='schedules')
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=SCHEDULE_STATUS_CHOICES, default='pending')
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    recipients_processed = models.PositiveIntegerField(default=0)
    
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    class Meta:
        db_table = 'campaign_schedules'
        ordering = ['-scheduled_at']
    
    def __str__(self):
        return f"{self.campaign.name} - {self.scheduled_at}"

class CampaignAnalytics(BaseModel):
    campaign = models.OneToOneField(Campaign, on_delete=models.CASCADE, related_name='analytics')
    
    email_sent = models.PositiveIntegerField(default=0)
    email_delivered = models.PositiveIntegerField(default=0)
    email_opened = models.PositiveIntegerField(default=0)
    email_clicked = models.PositiveIntegerField(default=0)
    email_bounced = models.PositiveIntegerField(default=0)
    
    whatsapp_sent = models.PositiveIntegerField(default=0)
    whatsapp_delivered = models.PositiveIntegerField(default=0)
    whatsapp_read = models.PositiveIntegerField(default=0)
    whatsapp_replied = models.PositiveIntegerField(default=0)
    
    sms_sent = models.PositiveIntegerField(default=0)
    sms_delivered = models.PositiveIntegerField(default=0)
    sms_replied = models.PositiveIntegerField(default=0)
    
    total_responses = models.PositiveIntegerField(default=0)
    interested_responses = models.PositiveIntegerField(default=0)
    not_interested_responses = models.PositiveIntegerField(default=0)
    callback_requests = models.PositiveIntegerField(default=0)
    complaints = models.PositiveIntegerField(default=0)
    unsubscribes = models.PositiveIntegerField(default=0)
    
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    cost_per_recipient = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.0000'))

    conversions = models.PositiveIntegerField(default=0)
    revenue_generated = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'campaign_analytics'
    
    def __str__(self):
        return f"Analytics - {self.campaign.name}"

class CampaignFeedback(BaseModel):
    """Customer feedback on campaigns"""
    FEEDBACK_TYPE_CHOICES = [
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
        ('complaint', 'Complaint'),
        ('suggestion', 'Suggestion'),
    ]
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='feedback')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES)
    rating = models.PositiveIntegerField(null=True, blank=True, help_text="Rating from 1-5")
    feedback_text = models.TextField()
    
    channel_received = models.CharField(max_length=20, choices=Campaign.CHANNEL_CHOICES)
    received_at = models.DateTimeField(auto_now_add=True)
    
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = 'campaign_feedback'
        ordering = ['-received_at']
    
    def __str__(self):
        return f"Feedback - {self.campaign.name} from {self.customer.full_name}"

class CampaignAutomation(BaseModel):
    """Automated campaign triggers"""
    TRIGGER_TYPE_CHOICES = [
        ('policy_expiry', 'Policy Expiry'),
        ('payment_due', 'Payment Due'),
        ('new_customer', 'New Customer'),
        ('claim_status', 'Claim Status Change'),
        ('birthday', 'Customer Birthday'),
        ('anniversary', 'Policy Anniversary'),
    ]
    
    name = models.CharField(max_length=200)
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES)
    campaign_template = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='automations')
    
    trigger_conditions = models.JSONField(default=dict)
    
    delay_days = models.PositiveIntegerField(default=0)
    delay_hours = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    total_triggered = models.PositiveIntegerField(default=0)
    last_triggered = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    class Meta:
        db_table = 'campaign_automations'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.trigger_type})"


class CampaignScheduleInterval(BaseModel):    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('push', 'Push Notification'),
    ]
    
    DELAY_UNIT_CHOICES = [
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
    ]
    
    TRIGGER_CONDITION_CHOICES = [
        ('no_response', 'Send if no response to previous message'),
        ('no_action', 'Send if no action taken (click/conversion)'),
        ('no_engagement', 'Send if no engagement (open/click)'),
        ('always', 'Always send (regardless of previous response)'),
    ]
    
    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.CASCADE, 
        related_name='schedule_intervals',
        help_text="Campaign this schedule interval belongs to"
    )
    template = models.ForeignKey(
        Template, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='campaign_schedules',
        help_text="Template to use for this interval"
    )
    sequence_order = models.PositiveIntegerField(
        default=1,
        help_text="Order of this interval in the sequence (1, 2, 3, etc.)"
    )
    channel = models.CharField(
        max_length=20, 
        choices=CHANNEL_CHOICES,
        help_text="Communication channel for this interval"
    )
    delay_value = models.PositiveIntegerField(
        default=1,
        help_text="Delay value (number)"
    )
    delay_unit = models.CharField(
        max_length=10,
        choices=DELAY_UNIT_CHOICES,
        default='days',
        help_text="Delay unit (minutes, hours, days, weeks)"
    )
    
    trigger_conditions = models.JSONField(
        default=list,
        help_text="List of trigger conditions for this interval"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schedule interval is active"
    )
    is_sent = models.BooleanField(
        default=False,
        help_text="Whether this interval has been sent"
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this interval is scheduled to be sent"
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this interval was actually sent"
    )
    class Meta:
        db_table = 'campaign_schedule_intervals'
        ordering = ['campaign', 'sequence_order']
        indexes = [
            models.Index(fields=['campaign', 'sequence_order']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['is_active', 'is_sent']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'sequence_order'],
                name='unique_campaign_sequence_order'
            )
        ]
    
    def __str__(self):
        return f"{self.campaign.name} - {self.get_channel_display()} (Interval {self.sequence_order})"
    
    def get_delay_description(self):
        """Get human-readable delay description"""
        unit = self.delay_unit
        if self.delay_value == 1:
            unit = unit.rstrip('s') 
        return f"After {self.delay_value} {unit}"
    
    def calculate_scheduled_time(self, base_time=None):
        """Calculate when this interval should be scheduled"""
        if base_time is None:
            base_time = timezone.now()
        
        if self.delay_unit == 'minutes':
            return base_time + timedelta(minutes=self.delay_value)
        elif self.delay_unit == 'hours':
            return base_time + timedelta(hours=self.delay_value)
        elif self.delay_unit == 'days':
            return base_time + timedelta(days=self.delay_value)
        elif self.delay_unit == 'weeks':
            return base_time + timedelta(weeks=self.delay_value)
        
        return base_time
    
    def should_send(self, recipient):
        """Check if this interval should be sent for a specific recipient"""
        if not self.is_active or self.is_sent:
            return False
        for condition in self.trigger_conditions:
            if condition == 'no_response':
                previous_intervals = CampaignScheduleInterval.objects.filter(
                    campaign=self.campaign,
                    sequence_order__lt=self.sequence_order,
                    is_sent=True
                ).order_by('sequence_order')
                
                for prev_interval in previous_intervals:
                    pass
                    
            elif condition == 'no_action':
                pass
                
            elif condition == 'no_engagement':
                pass
                
            elif condition == 'always':
                return True
        
        return True  