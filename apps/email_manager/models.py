from django.db import models
from apps.core.models import BaseModel
from apps.templates.models import Template


class EmailManager(BaseModel):
    PRIORITY_CHOICES = [
        ('Normal', 'Normal'),
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]
    
    to = models.EmailField(
        max_length=255,
        help_text="Primary recipient email address"
    )
    cc = models.TextField(
        blank=True,
        null=True,
        help_text="CC recipient email addresses (comma-separated, optional)"
    )
    bcc = models.TextField(
        blank=True,
        null=True,
        help_text="BCC recipient email addresses (comma-separated, optional)"
    )
    
    subject = models.CharField(
        max_length=500,
        help_text="Email subject line"
    )
    message = models.TextField(
        help_text="Email message body content"
    )
    
    policy_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Associated policy number"
    )
    customer_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Customer name"
    )
    renewal_date = models.DateField(
        blank=True,
        null=True,
        help_text="Policy renewal date"
    )
    premium_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Premium amount"
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='Normal',
        help_text="Email priority level"
    )
    schedule_send = models.BooleanField(
        default=False,
        help_text="Whether to schedule the email for later sending"
    )
    schedule_date_time = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Scheduled date and time for sending the email"
    )
    
    track_opens = models.BooleanField(
        default=False,
        help_text="Whether to track email opens"
    )
    track_clicks = models.BooleanField(
        default=False,
        help_text="Whether to track email link clicks"
    )
    
    email_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
            ('scheduled', 'Scheduled'),
        ],
        default='pending',
        help_text="Status of the email"
    )
    sent_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date and time when email was sent"
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if email sending failed"
    )
    
    template = models.ForeignKey(
        Template,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_managers',
        db_column='templates_id',
        help_text="Associated template"
    )

    
    class Meta:
        db_table = 'email_manager'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['to']),
            models.Index(fields=['policy_number']),
            models.Index(fields=['priority']),
            models.Index(fields=['schedule_send', 'schedule_date_time']),
            models.Index(fields=['email_status']),
            models.Index(fields=['template']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Email to {self.to} - {self.subject}"

