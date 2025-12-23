from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils import timezone
from .utils import _get_fernet, encrypt_credential, decrypt_credential, apply_provider_defaults
from cryptography.fernet import InvalidToken
PRIORITY_CHOICES = [
    ('high', 'High'),
    ('medium', 'Medium'),
    ('low', 'Low'),
]

CATEGORY_CHOICES = [
    ('refund', 'Refund'),
    ('complaint', 'Complaint'),
    ('appointment', 'Appointment'),
    ('feedback', 'Feedback'),
    ('uncategorized', 'Uncategorized'),
]

PROVIDER_CHOICES = [
    ('gmail', 'Gmail'),
    ('outlook', 'Outlook/Office 365'),
    ('yahoo', 'Yahoo Mail'),
    ('custom', 'Custom IMAP/SMTP'),
]

SYNC_INTERVAL_CHOICES = [
    (1, '1 Minute'),
    (5, '5 Minutes'),
    (10, '10 Minutes'),
    (15, '15 Minutes'),
    (30, '30 Minutes'),
    (60, '1 Hour'),
]

# --- NEW: Choices for the Fallback Logic ---
SENDING_METHOD_CHOICES = [
    ('smtp', 'Use Incoming SMTP Credentials (Gmail/Outlook)'),
    ('system_default', 'Use System Default Provider (e.g. Corp SendGrid)'),
    ('specific_provider', 'Use Specific Provider (Override)'),
]

class EmailAccount(models.Model):
    """
    Stores configuration for a single connected email account (IMAP/SMTP).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text="The owner of this configuration.")
    account_name = models.CharField(max_length=100, help_text="A friendly name for the account (e.g., 'Support Inbox').")
    email_address = models.EmailField(unique=True)
    email_provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='gmail')
    
    # IMAP Settings (Incoming)
    imap_server = models.CharField(max_length=255, blank=True)
    imap_port = models.IntegerField(default=993, validators=[MinValueValidator(1), MaxValueValidator(65535)])
    
    # SMTP Settings (Outgoing)
    smtp_server = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587, validators=[MinValueValidator(1), MaxValueValidator(65535)])
    
    # Sync Settings
    use_ssl_tls = models.BooleanField(default=True, help_text="Use SSL/TLS encryption for connections.")
    auto_sync_enabled = models.BooleanField(default=True)
    sync_interval_minutes = models.IntegerField(choices=SYNC_INTERVAL_CHOICES, default=5)

    connection_status = models.BooleanField(default=False, help_text="True if the last connection test was successful.")
    last_sync_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of the last successful sync or test.")
    last_sync_log = models.TextField(blank=True, help_text="Stores the error message if the connection failed.")

    # --- NEW SENDING CONFIGURATION ---
    sending_method = models.CharField(
        max_length=20, 
        choices=SENDING_METHOD_CHOICES, 
        default='smtp',
        help_text="Determines how emails are sent from this account."
    )
    specific_provider = models.ForeignKey(
        'email_provider.EmailProviderConfig', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="If 'Use Specific Provider' is selected, this provider will be used."
    )

    # Helper to auto-select this account in Campaigns
    is_default_sender = models.BooleanField(
        default=False, 
        help_text="If true, this account is pre-selected as the 'From' address in new campaigns."
    )
    # ---------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    access_credential = models.CharField(
        max_length=512, 
        help_text="The encrypted App Password or OAuth Token provided by the email service for connection."
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_accounts')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_accounts')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_accounts')
    
    class Meta:
        db_table = 'email_settings_accounts'
        verbose_name = "Email Account"
        verbose_name_plural = "Email Accounts"
        unique_together = ('user', 'email_address') 

    def __str__(self):
        return f"{self.account_name} ({self.email_address})"

    def save(self, *args, **kwargs):
        apply_provider_defaults(self)

        if self.access_credential:
            try:
                f = _get_fernet()
                f.decrypt(self.access_credential.encode())
            except (InvalidToken, ValueError, AttributeError):
                self.access_credential = encrypt_credential(self.access_credential)
 
        if self.is_default_sender:
            EmailAccount.objects.filter(user=self.user, is_default_sender=True).exclude(pk=self.pk).update(is_default_sender=False)

        super().save(*args, **kwargs)

    def get_decrypted_credential(self):
        return decrypt_credential(self.access_credential)

    def soft_delete(self, user):
        """Soft deletes the instance."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()

# ... (EmailModuleSettings, ClassificationRule, EmailMessage remain the same)
class EmailModuleSettings(models.Model):
    """
    Stores general, global, processing, and AI features settings, unique per user.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    
    # Connection Settings
    imap_connection_status = models.BooleanField(default=False, help_text="Status of the main IMAP test connection.")
    enable_webhook_notifications = models.BooleanField(default=False)
    webhook_url = models.URLField(max_length=500, blank=True, null=True)
    
    # Mail Merge Configuration
    enable_mail_merge = models.BooleanField(default=False)
    auto_generate_documents = models.BooleanField(default=False, help_text="Automatically create documents during bulk email campaigns")
    attach_to_emails = models.BooleanField(default=True, help_text="Automatically attach generated documents to emails")
    document_storage_path = models.CharField(max_length=255, default="/documents/templates")
    output_directory = models.CharField(max_length=255, default="/documents/generated")
    
    # Processing Settings
    email_polling_interval_minutes = models.IntegerField(choices=SYNC_INTERVAL_CHOICES, default=5)
    auto_categorization_enabled = models.BooleanField(default=True)
    fallback_tagging_enabled = models.BooleanField(default=True)
    
    # Inbox Preferences
    emails_per_page = models.IntegerField(default=25, validators=[MinValueValidator(10), MaxValueValidator(100)])
    auto_refresh_inbox = models.BooleanField(default=True)
    mark_read_on_open = models.BooleanField(default=True)
    
    # AI Features
    ai_intent_classification = models.BooleanField(default=True)
    ai_sentiment_analysis = models.BooleanField(default=True)
    ai_realtime_collaboration = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_module_settings')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_module_settings')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_module_settings')


    class Meta:
        db_table = 'email_module_settings'
        verbose_name = "Email Module Settings"
        verbose_name_plural = "Email Module Settings"

    def __str__(self):
        return f"Settings for {self.user.username}"

class ClassificationRule(models.Model):
    """
    Stores keyword-based rules for automatic email classification.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    keyword = models.CharField(max_length=100, help_text="Keyword to match in email subject or content.")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='uncategorized')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_enabled = models.BooleanField(default=True, help_text="Enable or disable this classification rule.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_classification_rules')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_classification_rules')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_classification_rules')

    class Meta:
        db_table = 'email_settings_classification_rules'
        verbose_name = "Classification Rule"
        verbose_name_plural = "Classification Rules"
        unique_together = ('user', 'keyword')

    def __str__(self):
        return f"Rule: '{self.keyword}' -> {self.category} ({self.priority})"
    
    def soft_delete(self, user):
        """Soft deletes the instance."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()


class EmailMessage(models.Model):
    """
    Stores individual email messages fetched from connected accounts.
    """
    email_account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=255, unique=True, help_text="Unique ID from the email provider to prevent duplicates.")
    subject = models.CharField(max_length=998, blank=True)
    sender = models.CharField(max_length=255)
    recipient = models.CharField(max_length=998)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField()
    
    is_read = models.BooleanField(default=False)
    folder = models.CharField(max_length=50, default='INBOX')
    
    # Auto-classification fields
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='uncategorized')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_processed = models.BooleanField(default=False, help_text="True if AI/Rules have already run on this email.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['message_id']),
            models.Index(fields=['email_account', 'received_at']),
        ]

    def __str__(self):
        return f"[{self.email_account.account_name}] {self.subject[:50]}"