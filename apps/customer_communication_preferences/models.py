from django.db import models
from django.core.validators import RegexValidator
from apps.core.models import BaseModel
from apps.customers.models import Customer


class CustomerCommunicationPreference(BaseModel):
    COMMUNICATION_CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('whatsapp', 'WhatsApp'),
        ('postal_mail', 'Postal Mail'),
        ('in_app', 'In-App Notification'),
        ('push_notification', 'Push Notification'),
    ]
    
    FREQUENCY_CHOICES = [
        ('immediate', 'Immediate'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('never', 'Never'),
    ]
    
    COMMUNICATION_TYPE_CHOICES = [
        ('policy_renewal', 'Policy Renewal'),
        ('payment_reminder', 'Payment Reminder'),
        ('policy_expiry', 'Policy Expiry'),
        ('claim_updates', 'Claim Updates'),
        ('promotional', 'Promotional'),
        ('newsletter', 'Newsletter'),
        ('system_alerts', 'System Alerts'),
        ('customer_service', 'Customer Service'),
        ('emergency_alerts', 'Emergency Alerts'),
        ('policy_updates', 'Policy Updates'),
        ('birthday_wishes', 'Birthday Wishes'),
        ('survey_feedback', 'Survey & Feedback'),
    ]
    
    TIME_PREFERENCE_CHOICES = [
        ('morning', 'Morning (8 AM - 12 PM)'),
        ('afternoon', 'Afternoon (12 PM - 5 PM)'),
        ('evening', 'Evening (5 PM - 8 PM)'),
        ('night', 'Night (8 PM - 10 PM)'),
        ('anytime', 'Anytime'),
        ('business_hours', 'Business Hours Only'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('mr', 'Marathi'),
        ('gu', 'Gujarati'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
        ('kn', 'Kannada'),
        ('ml', 'Malayalam'),
        ('bn', 'Bengali'),
        ('pa', 'Punjabi'),
        ('or', 'Odia'),
        ('as', 'Assamese'),
    ]
    
    # Foreign Key to Customer
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='detailed_communication_preferences',
        help_text="Customer these preferences belong to"
    )
    
    # Communication Channel Preferences
    preferred_channel = models.CharField(
        max_length=20,
        choices=COMMUNICATION_CHANNEL_CHOICES,
        default='email',
        help_text="Primary preferred communication channel"
    )
    
    secondary_channel = models.CharField(
        max_length=20,
        choices=COMMUNICATION_CHANNEL_CHOICES,
        blank=True,
        help_text="Secondary communication channel"
    )
    
    # Communication Type and Frequency
    communication_type = models.CharField(
        max_length=30,
        choices=COMMUNICATION_TYPE_CHOICES,
        help_text="Type of communication this preference applies to"
    )
    
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='immediate',
        help_text="How frequently customer wants to receive this type of communication"
    )
    
    # Channel-specific preferences
    email_enabled = models.BooleanField(
        default=True,
        help_text="Whether customer wants email communications"
    )
    
    sms_enabled = models.BooleanField(
        default=True,
        help_text="Whether customer wants SMS communications"
    )
    
    phone_enabled = models.BooleanField(
        default=True,
        help_text="Whether customer wants phone call communications"
    )
    
    whatsapp_enabled = models.BooleanField(
        default=False,
        help_text="Whether customer wants WhatsApp communications"
    )
    
    postal_mail_enabled = models.BooleanField(
        default=False,
        help_text="Whether customer wants postal mail communications"
    )
    
    push_notification_enabled = models.BooleanField(
        default=True,
        help_text="Whether customer wants push notifications"
    )
    
    # Time and Language Preferences
    preferred_time = models.CharField(
        max_length=20,
        choices=TIME_PREFERENCE_CHOICES,
        default='business_hours',
        help_text="Preferred time for receiving communications"
    )
    
    preferred_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='en',
        help_text="Preferred language for communications"
    )
    
    # Contact Information Override
    alternate_email = models.EmailField(
        blank=True,
        help_text="Alternate email for specific communication types"
    )
    
    alternate_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
        help_text="Alternate phone number for specific communication types"
    )
    
    # Do Not Disturb Settings
    do_not_disturb = models.BooleanField(
        default=False,
        help_text="Whether customer is in do not disturb mode"
    )
    
    dnd_start_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time for do not disturb period"
    )
    
    dnd_end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="End time for do not disturb period"
    )
    
    # Special Preferences
    marketing_consent = models.BooleanField(
        default=True,
        help_text="Whether customer consents to marketing communications"
    )
    
    data_sharing_consent = models.BooleanField(
        default=False,
        help_text="Whether customer consents to data sharing for communications"
    )
    
    # Additional Settings
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this preference setting is active"
    )
    
    priority_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        default='medium',
        help_text="Priority level for this communication type"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about customer communication preferences"
    )
    
    class Meta:
        db_table = 'customer_communication_preferences'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['preferred_channel']),
            models.Index(fields=['communication_type']),
            models.Index(fields=['frequency']),
            models.Index(fields=['is_active']),
            models.Index(fields=['marketing_consent']),
            models.Index(fields=['do_not_disturb']),
        ]
        unique_together = ['customer', 'communication_type']
    
    def __str__(self):
        return f"{self.customer.full_name} - {self.get_communication_type_display()} via {self.get_preferred_channel_display()}"
    
    @property
    def communication_summary(self):
        """Return a summary of communication preferences"""
        channels = []
        if self.email_enabled:
            channels.append('Email')
        if self.sms_enabled:
            channels.append('SMS')
        if self.phone_enabled:
            channels.append('Phone')
        if self.whatsapp_enabled:
            channels.append('WhatsApp')
        if self.postal_mail_enabled:
            channels.append('Postal')
        if self.push_notification_enabled:
            channels.append('Push')
        
        return f"{', '.join(channels)} | {self.get_frequency_display()} | {self.get_preferred_time_display()}"
    
    @property
    def is_contactable(self):
        """Check if customer can be contacted based on preferences"""
        if self.do_not_disturb:
            return False
        
        return any([
            self.email_enabled,
            self.sms_enabled,
            self.phone_enabled,
            self.whatsapp_enabled,
            self.postal_mail_enabled,
            self.push_notification_enabled
        ])
    
    def get_enabled_channels(self):
        """Get list of enabled communication channels"""
        enabled_channels = []
        
        if self.email_enabled:
            enabled_channels.append('email')
        if self.sms_enabled:
            enabled_channels.append('sms')
        if self.phone_enabled:
            enabled_channels.append('phone')
        if self.whatsapp_enabled:
            enabled_channels.append('whatsapp')
        if self.postal_mail_enabled:
            enabled_channels.append('postal_mail')
        if self.push_notification_enabled:
            enabled_channels.append('push_notification')
            
        return enabled_channels


class CommunicationLog(BaseModel):
    """Log of all communication attempts with customers"""
    
    COMMUNICATION_CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('whatsapp', 'WhatsApp'),
        ('postal_mail', 'Postal Mail'),
        ('in_app', 'In-App Notification'),
        ('push_notification', 'Push Notification'),
    ]
    
    OUTCOME_CHOICES = [
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('no_response', 'No Response'),
        ('busy', 'Busy'),
        ('invalid_number', 'Invalid Number'),
        ('blocked', 'Blocked'),
        ('opt_out', 'Opted Out'),
        ('delivered', 'Delivered'),
        ('bounced', 'Bounced'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('replied', 'Replied'),
    ]
    
    # Foreign Key to Customer
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='communication_logs',
        help_text="Customer this communication was sent to"
    )
    
    # Communication Details
    channel = models.CharField(
        max_length=20,
        choices=COMMUNICATION_CHANNEL_CHOICES,
        help_text="Communication channel used"
    )
    
    communication_date = models.DateTimeField(
        help_text="Date and time of communication attempt"
    )
    
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        help_text="Result of the communication attempt"
    )
    
    # Additional Details
    message_content = models.TextField(
        blank=True,
        help_text="Content of the message sent (optional)"
    )
    
    response_received = models.TextField(
        blank=True,
        help_text="Customer response if any (optional)"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the communication"
    )
    
    # System Fields
    initiated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_communications',
        help_text="User who initiated this communication"
    )
    
    # Duration
    duration_in_minutes = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Duration of the call/interaction in minutes"
    )
    class Meta:
        db_table = 'communication_logs'
        ordering = ['-communication_date']
        indexes = [
            models.Index(fields=['customer', 'communication_date']),
            models.Index(fields=['channel', 'outcome']),
            models.Index(fields=['communication_date']),
        ]
    
    def __str__(self):
        return f"{self.customer.full_name} - {self.get_channel_display()} - {self.get_outcome_display()}"
    
    @property
    def customer_name(self):
        """Return customer's full name for easy access"""
        return self.customer.full_name if self.customer else None