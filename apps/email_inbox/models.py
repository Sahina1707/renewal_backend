from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
import uuid

User = get_user_model()


class EmailFolder(models.Model):
    """Email folders for organizing messages"""
    
    FOLDER_TYPES = [
        ('inbox', 'Inbox'),
        ('sent', 'Sent'),
        ('drafts', 'Drafts'),
        ('trash', 'Trash'),
        ('spam', 'Spam'),
        ('junk', 'Junk'),
        ('archive', 'Archive'),
        ('custom', 'Custom'),
    ]
    # CUSTOMER_TYPE_CHOICES = [
    #     ('normal', 'Normal'),
    #     ('hni', 'HNI (High Net Worth)'),
    #     ('super_hni', 'Super HNI'),
    #     ('vip', 'VIP'),
    # ]
    # customer_type = models.CharField(
    #     max_length=20,
    #     choices=CUSTOMER_TYPE_CHOICES,
    #     default='normal',
    #     help_text="Customer categorization for support tiers"
    # )

    # ESCALATION_PRIORITY_CHOICES = [
    #     ('high', 'High Priority'),
    #     ('urgent', 'Urgent Priority'),
    #     ('critical', 'Critical Priority'),
    # ]
    # is_escalated = models.BooleanField(default=False)
    # escalation_reason = models.TextField(blank=True, null=True)
    # escalation_priority = models.CharField(
    #     max_length=20,
    #     choices=ESCALATION_PRIORITY_CHOICES,
    #     blank=True,
    #     null=True
    # )
    # escalated_at = models.DateTimeField(blank=True, null=True)
    # escalated_by = models.ForeignKey(
    #     User, 
    #     on_delete=models.SET_NULL, 
    #     null=True, 
    #     related_name='escalated_emails'
    # )
    # due_date = models.DateTimeField(null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    folder_type = models.CharField(max_length=20, choices=FOLDER_TYPES, default='custom')
    description = models.TextField(blank=True, null=True)
    is_system = models.BooleanField(default=False, help_text="System-created folder")
    is_active = models.BooleanField(default=True)
    
    # Hierarchy
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    sort_order = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_folders')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_folders')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_folders')
    
    class Meta:
        db_table = 'email_folders'
        ordering = ['sort_order', 'name']
        unique_together = ['name', 'parent']
        verbose_name = 'Email Folder'
        verbose_name_plural = 'Email Folders'
    
    def __str__(self):
        return self.name
    
    def soft_delete(self):
        """Soft delete the folder"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])


class EmailInboxMessage(models.Model):
    """Incoming email messages"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('forwarded', 'Forwarded'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
        ('draft', 'Draft'),
        ('restored', 'Restored'),
    ]
    
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('policy_renewal', 'Policy Renewal'),
        ('claim', 'Claim'),
        ('payment', 'Payment'),
        ('complaint', 'Complaint'),
        ('inquiry', 'Inquiry'),
        ('feedback', 'Feedback'),
        ('marketing', 'Marketing'),
        ('system', 'System'),
        ('refund', 'Refund'),            
        ('appointment', 'Appointment'),  
        ('uncategorized', 'Uncategorized'),
    ]
    
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    ]
    
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='uncategorized'
    )
    
    id = models.BigAutoField(primary_key=True)
    message_id = models.CharField(max_length=255, unique=True, help_text="Unique message identifier")
    custom_id = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Auto-generated ID like EMAIL-0001")
    
    # Email headers
    from_email = models.EmailField()
    from_name = models.CharField(max_length=200, blank=True, null=True)
    to_emails = models.JSONField(default=list, blank=True, help_text="List of recipient email addresses")
    cc_emails = models.JSONField(default=list, blank=True)
    bcc_emails = models.JSONField(default=list, blank=True)
    reply_to = models.EmailField(blank=True, null=True)
    
    # Email content
    subject = models.CharField(max_length=500)
    html_content = models.TextField(blank=True, null=True)
    text_content = models.TextField(blank=True, null=True)
    
    # Classification
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, default='neutral')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    
    # Organization
    folder = models.ForeignKey(EmailFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    is_starred = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True, help_text="Custom tags")
    
    # Threading
    thread_id = models.CharField(max_length=255, blank=True, null=True, help_text="Thread identifier")
    in_reply_to = models.CharField(max_length=255, blank=True, null=True, help_text="In-Reply-To header")
    references = models.CharField(max_length=500, blank=True, null=True, help_text="References header")
    
    # Processing
    
    # Email metadata
    received_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    
    # Additional fields
    is_spam = models.BooleanField(default=False)
    is_phishing = models.BooleanField(default=False)
    subcategory = models.CharField(max_length=50, blank=True, null=True)
    confidence_score = models.FloatField(default=0.0)
    attachments = models.JSONField(default=list, blank=True)
    attachment_count = models.PositiveIntegerField(default=0)
    is_processed = models.BooleanField(default=False)
    processing_notes = models.TextField(blank=True, null=True)
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_emails'
    )
    forwarded_at = models.DateTimeField(blank=True, null=True)
    
    # Raw email data
    raw_headers = models.JSONField(default=dict, blank=True)
    raw_body = models.TextField(blank=True, null=True)
    headers = models.JSONField(default=dict, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=50, default='webhook')
    source_message_id = models.CharField(max_length=255, blank=True, null=True)
        
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_inbox_messages')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_inbox_messages')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_inbox_messages')
    is_escalated = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True, null=True)
    escalation_priority = models.CharField(
        max_length=20,
        choices=[('high', 'High'), ('urgent', 'Urgent'), ('critical', 'Critical')],
        blank=True, null=True
    )
    escalated_at = models.DateTimeField(blank=True, null=True)
    escalated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='escalated_inbox_messages' 
    )
    due_date = models.DateTimeField(null=True, blank=True)
    parent_message = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='replies'
    )
    
    # Customer Type (Required for the dashboard filters)
    CUSTOMER_TYPE_CHOICES = [
        ('normal', 'Normal'),
        ('hni', 'HNI'),
        ('super_hni', 'Super HNI'),
        ('vip', 'VIP'),
    ]
    customer_type = models.CharField(
        max_length=20, 
        choices=CUSTOMER_TYPE_CHOICES, 
        default='normal'
    )
    class Meta:
        db_table = 'email_inbox_messages'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['from_email', 'received_at']),
            models.Index(fields=['thread_id', 'received_at']),
            models.Index(fields=['is_starred', 'received_at']),
        ]
        verbose_name = 'Email Inbox Message'
        verbose_name_plural = 'Email Inbox Messages'
    
    def __str__(self):
        return f"{self.subject} from {self.from_email}"
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.custom_id:
            self.custom_id = f"EMAIL-{self.id:04d}"
            # Update DB directly to avoid recursion or double signals
            EmailInboxMessage.objects.filter(id=self.id).update(custom_id=self.custom_id)

    def mark_as_read(self):
        """Mark message as read"""
        if self.status == 'unread':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])
    
    def mark_as_replied(self):
        """Mark message as replied"""
        self.status = 'replied'
        self.replied_at = timezone.now()
        self.save(update_fields=['status', 'replied_at'])
    
    def mark_as_forwarded(self):
        """Mark message as forwarded"""
        self.status = 'forwarded'
        self.forwarded_at = timezone.now()
        self.save(update_fields=['status', 'forwarded_at'])
    
    def soft_delete(self):
        """Soft delete the message"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.status = 'deleted'
        self.save(update_fields=['is_deleted', 'deleted_at', 'status'])


class EmailConversation(models.Model):
    """Email conversation threads"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread_id = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=500)
    
    # Participants
    participants = models.JSONField(default=list, help_text="List of email addresses in conversation")
    
    # Statistics
    message_count = models.PositiveIntegerField(default=0)
    unread_count = models.PositiveIntegerField(default=0)
    
    # Latest activity
    last_message_at = models.DateTimeField(blank=True, null=True)
    last_message_from = models.EmailField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_conversations'
        ordering = ['-last_message_at']
        verbose_name = 'Email Conversation'
        verbose_name_plural = 'Email Conversations'
    
    def __str__(self):
        return f"Conversation: {self.subject}"


class EmailFilter(models.Model):
    """Email filters for automatic organization"""
    
    FILTER_TYPES = [
        ('subject', 'Subject'),
        ('from', 'From'),
        ('to', 'To'),
        ('body', 'Body'),
        ('category', 'Category'),
        ('priority', 'Priority'),
    ]
    
    OPERATORS = [
        ('contains', 'Contains'),
        ('not_contains', 'Does not contain'),
        ('equals', 'Equals'),
        ('not_equals', 'Does not equal'),
        ('starts_with', 'Starts with'),
        ('ends_with', 'Ends with'),
        ('regex', 'Regular expression'),
    ]
    
    ACTIONS = [
        ('move_to_folder', 'Move to folder'),
        ('mark_as_read', 'Mark as read'),
        ('mark_as_important', 'Mark as important'),
        ('add_tag', 'Add tag'),
        ('assign_to', 'Assign to user'),
        ('auto_reply', 'Auto reply'),
        ('forward', 'Forward'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Filter conditions
    filter_type = models.CharField(max_length=20, choices=FILTER_TYPES)
    operator = models.CharField(max_length=20, choices=OPERATORS)
    value = models.CharField(max_length=500)
    
    # Actions
    action = models.CharField(max_length=20, choices=ACTIONS)
    action_value = models.CharField(max_length=500, blank=True, null=True, help_text="Action parameter (folder name, tag, etc.)")
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="System-created filter")
    priority = models.PositiveIntegerField(default=0, help_text="Filter priority (higher = processed first)")
    
    # Statistics
    match_count = models.PositiveIntegerField(default=0)
    last_matched = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_filters')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_filters')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_filters')
    
    class Meta:
        db_table = 'email_filters'
        ordering = ['-priority', 'name']
        verbose_name = 'Email Filter'
        verbose_name_plural = 'Email Filters'
    
    def __str__(self):
        return self.name
    
    def soft_delete(self):
        """Soft delete the filter"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])


class EmailAttachment(models.Model):
    """Email attachments"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_message = models.ForeignKey(EmailInboxMessage, on_delete=models.CASCADE, related_name='email_attachments')
    
    # File information
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_path = models.CharField(max_length=500, help_text="Path to stored file")
    
    # Security
    is_safe = models.BooleanField(default=True, help_text="File passed security scan")
    scan_result = models.JSONField(default=dict, blank=True, help_text="Security scan results")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_attachments')
    
    class Meta:
        db_table = 'email_attachments'
        ordering = ['filename']
        verbose_name = 'Email Attachment'
        verbose_name_plural = 'Email Attachments'
    
    def __str__(self):
        return f"{self.filename} ({self.email_message.subject})"


class EmailSearchQuery(models.Model):
    """Saved email search queries"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Search parameters
    query_params = models.JSONField(default=dict, help_text="Search parameters")
    
    # Settings
    is_public = models.BooleanField(default=False, help_text="Available to all users")
    is_active = models.BooleanField(default=True)
    
    # Usage statistics
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_email_search_queries')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_email_search_queries')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_email_search_queries')
    
    class Meta:
        db_table = 'email_search_queries'
        ordering = ['-last_used', 'name']
        verbose_name = 'Email Search Query'
        verbose_name_plural = 'Email Search Queries'
    
    def __str__(self):
        return self.name
    
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=['usage_count', 'last_used'])
    
    def soft_delete(self):
        """Soft delete the search query"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])
class EmailAuditLog(models.Model):
    email_message = models.ForeignKey(EmailInboxMessage, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50, help_text="e.g., 'Viewed', 'Escalated', 'Category Changed'")
    details = models.TextField(blank=True, null=True, help_text="Extra info like 'Changed from Normal to VIP'")
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'email_audit_logs' 
        ordering = ['-timestamp']

class EmailInternalNote(models.Model):
    """
    Internal notes for collaboration (matches the 'Add Note' feature in video)
    """
    email_message = models.ForeignKey(EmailInboxMessage, on_delete=models.CASCADE, related_name='internal_notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'email_internal_notes'
        ordering = ['-created_at']
class BulkEmailCampaign(models.Model):
    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('forwarded', 'Forwarded'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
        ('draft', 'Draft'),
        ('restored', 'Restored'),
        ('failed', 'Failed'), 
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    
    # Template Snapshot Fields (Subject/Body from template_id)
    subject_template = models.CharField(max_length=500, help_text="Base subject from template")
    body_html_template = models.TextField(help_text="Base HTML from template")
    
    custom_subject = models.CharField(max_length=500, blank=True, null=True, help_text="User's custom subject override")
    additional_message = models.TextField(blank=True, null=True, help_text="User's additional note")    
    # Recipient data
    recipients_data = models.JSONField(
        default=list, 
        help_text="List of dicts: [{'email': 'x', 'name': 'y', 'company': 'z'}]"
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Tracking
    total_recipients = models.IntegerField(default=0)
    successful_sends = models.IntegerField(default=0)
    failed_sends = models.IntegerField(default=0)
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bulk_email_campaigns'
        ordering = ['-created_at']