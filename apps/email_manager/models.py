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
    
    from_email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
        help_text="From email address used to send this email"
    )

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

    message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Unique message ID of the sent email"
    )
    
    started = models.BooleanField(
        default=False,
        help_text="Indicates whether the email sending process has started"
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
            models.Index(fields=['message_id']),
        ]
    
    def __str__(self):
        return f"Email to {self.to} - {self.subject}"

class EmailManagerInbox(BaseModel):
    from_email = models.EmailField(
        max_length=255,
        help_text="Sender email address"
    )
    to_email = models.TextField(
        help_text="Recipient email addresses (comma separated)"
    )
    subject = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Email subject"
    )
    message = models.TextField(
        blank=True,
        null=True,
        help_text="Plain text email body"
    )
    html_message = models.TextField(
        blank=True,
        null=True,
        help_text="HTML version of email body if available"
    )
    received_at = models.DateTimeField(
        help_text="Time when the email was received on the server"
    )
    message_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique message ID from email header"
    )
    in_reply_to = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Message-ID of the email this is replying to"
    )
    references = models.TextField(
        blank=True,
        null=True,
        help_text="Thread reference IDs"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Marks whether this email has been read"
    )
    attachments = models.JSONField(
        blank=True,
        null=True,
        help_text="Stores metadata of attachments (name, size, path)"
    )

    related_email = models.ForeignKey(
        'EmailManager',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='inbox_replies'
    )
    started = models.BooleanField(
        default=False,
        help_text="Indicates whether processing for this inbox email has started"
    )


    class Meta:
        db_table = 'email_manager_inbox'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['from_email']),
            models.Index(fields=['to_email']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f"From {self.from_email} - {self.subject or '(no subject)'}"

class EmailReply(BaseModel):
    inbox = models.ForeignKey(
        EmailManagerInbox,
        on_delete=models.CASCADE,
        related_name="replies"
    )

    to_email = models.EmailField()
    from_email = models.EmailField()  

    subject = models.CharField(max_length=255)
    message = models.TextField()
    html_message = models.TextField(null=True, blank=True)

    in_reply_to = models.CharField(max_length=255, null=True, blank=True)
    message_id = models.CharField(max_length=255, null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ]
    )

    class Meta:
        db_table = "emailmanager_inbox_replymail"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['inbox']),
            models.Index(fields=['to_email']),
            models.Index(fields=['from_email']),
            models.Index(fields=['message_id']),
        ]

    def __str__(self):
        return f"Reply to {self.to_email} | {self.subject}"
class StartedReplyMail(BaseModel):
    original_email_manager = models.ForeignKey(
        EmailManager, on_delete=models.CASCADE, null=True, blank=True,
        related_name="started_replies"
    )
    original_inbox_email = models.ForeignKey(
        EmailManagerInbox, on_delete=models.CASCADE, null=True, blank=True,
        related_name="started_replies"
    )

    to_email = models.CharField(max_length=255)
    from_email = models.CharField(max_length=255, default="renewals@intelipro.in")
    subject = models.CharField(max_length=255)
    message = models.TextField(null=True, blank=True)
    html_message = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "emailmanager_startedreply_mails"

    def __str__(self):
        return f"Reply to {self.original_email_manager or self.original_inbox_email}"