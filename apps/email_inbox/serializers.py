from rest_framework import serializers
from django.utils.html import strip_tags
from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery,EmailInternalNote,BulkEmailCampaign,EmailAuditLog,
    
)
from django.apps import apps
from django.utils.timesince import timesince
class EmailInternalNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    
    class Meta:
        model = EmailInternalNote
        fields = ['id', 'note', 'author', 'author_name', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


class EmailFolderSerializer(serializers.ModelSerializer):
    """Serializer for EmailFolder"""
    
    folder_type_display = serializers.CharField(source='get_folder_type_display', read_only=True)
    message_count = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmailFolder
        fields = [
            'id', 'name', 'folder_type', 'folder_type_display', 'description',
             'is_system', 'is_active'
            , 'sort_order',
            'message_count', 'unread_count', 'created_at', 'updated_at',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'is_deleted', 'deleted_at', 'deleted_by'
        ]
        read_only_fields = [
            'id', 'is_system', 'message_count', 'unread_count', 'created_at',
            'updated_at', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
        ]
    
    def get_message_count(self, obj):
        """Get count of messages in this folder"""
        return obj.messages.filter(is_deleted=False).count()
    
    def get_unread_count(self, obj):
        """Get count of unread messages in this folder"""
        return obj.messages.filter(is_deleted=False, status='unread').count()
    
    def create(self, validated_data):
        """Set created_by when creating a new folder"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Set updated_by when updating a folder"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for EmailAttachment"""
    
    file_size_display = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmailAttachment
        fields = [
            'id', 'email_message', 'filename', 'content_type', 'file_size',
            'file_size_display', 'file_path', 'is_safe', 'scan_result',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = [
            'id', 'file_size', 'is_safe', 'scan_result', 'created_at', 'created_by'
        ]
    
    def get_file_size_display(self, obj):
        """Format file size for display"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class EmailInboxMessageSerializer(serializers.ModelSerializer):
    """Serializer for EmailInboxMessage"""
    
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    sentiment_display = serializers.CharField(source='get_sentiment_display', read_only=True)
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    attachments = EmailAttachmentSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    escalated_by_name = serializers.CharField(source='escalated_by.get_full_name', read_only=True)
    internal_notes = EmailInternalNoteSerializer(many=True, read_only=True) 

    class Meta:
        model = EmailInboxMessage
        fields = [
            'id', 'message_id', 'from_email', 'from_name', 'to_emails',
            'cc_emails', 'bcc_emails', 'reply_to', 'subject', 'html_content',
            'text_content', 'category', 'category_display', 'priority',
            'priority_display', 'sentiment', 'sentiment_display', 'status',
            'status_display', 'folder', 'folder_name', 'is_starred',
            'is_important', 'tags', 'thread_id',
            #   'parent',
            'is_processed', 'processing_notes', 'assigned_to', 'assigned_to_name',
            'received_at', 'read_at', 'replied_at', 'forwarded_at',
            'raw_headers', 'raw_body', 'attachments', 'created_at', 'updated_at',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'is_deleted', 'deleted_at', 'deleted_by',
            'escalation_reason',
            'escalation_priority',
            'escalated_at',
            'escalated_by_name',
            'due_date',
            'is_escalated',
            'customer_type',
            'internal_notes',
        ]
        read_only_fields = [
            'id', 'message_id', 'received_at', 'read_at', 'replied_at',
            'forwarded_at', 'created_at', 'updatedparent_at', 'created_by',
            'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
        ]

class EmailInboxMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating EmailInboxMessage"""
    
    class Meta:
        model = EmailInboxMessage
        fields = [
            'from_email', 'from_name', 'to_emails', 'cc_emails', 'bcc_emails',
            'reply_to', 'subject', 'html_content', 'text_content', 'category',
            'priority', 'sentiment', 'folder', 'is_starred', 'is_important',
            'tags', 'thread_id', 
            #   'parent',
            #  'assigned_to',
            #    'raw_headers',
            # 'raw_body'
        ]
    
    def create(self, validated_data):
        """Create a new email inbox message"""
        import uuid
        validated_data['message_id'] = str(uuid.uuid4())
        validated_data['created_by'] = self.context['request'].user
        validated_data['in_reply_to'] = validated_data.get('in_reply_to', '') or ''
        validated_data['references'] = validated_data.get('references', '') or ''
        validated_data['subcategory'] = validated_data.get('subcategory', '') or ''
        validated_data['source_message_id'] = validated_data.get('source_message_id', '') or ''
        return super().create(validated_data)
        


class EmailInboxMessageUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating EmailInboxMessage"""
    
    class Meta:
        model = EmailInboxMessage
        fields = [
            'category', 'priority', 'sentiment', 'status', 'folder',
            'is_starred', 'is_important', 'tags', 'is_processed',
            'processing_notes',
            #   'assigned_to'
        ]
    
    def update(self, instance, validated_data):
        """Update an email inbox message"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailConversationSerializer(serializers.ModelSerializer):
    """Serializer for EmailConversation"""
    
    class Meta:
        model = EmailConversation
        fields = [
            'id', 'thread_id', 'subject', 'participants', 'message_count',
            'unread_count', 'last_message_at', 'last_message_from',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmailFilterSerializer(serializers.ModelSerializer):
    """Serializer for EmailFilter"""
    
    filter_type_display = serializers.CharField(source='get_filter_type_display', read_only=True)
    operator_display = serializers.CharField(source='get_operator_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmailFilter
        fields = [
            'id', 'name', 'description', 'filter_type', 'filter_type_display',
            'operator', 'operator_display', 'value', 'action', 'action_display',
            'action_value', 'is_active', 'is_system', 'priority', 'match_count',
            'last_matched', 'created_at', 'updated_at', 'created_by',
            'created_by_name', 'updated_by', 'updated_by_name', 'is_deleted',
            'deleted_at', 'deleted_by'
        ]
        read_only_fields = [
            'id', 'match_count', 'last_matched', 'created_at',
            'updated_at', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
        ]
    
    def create(self, validated_data):
        """Set created_by when creating a new filter"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Set updated_by when updating a filter"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailSearchQuerySerializer(serializers.ModelSerializer):
    """Serializer for EmailSearchQuery"""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmailSearchQuery
        fields = [
            'id', 'name', 'description', 'query_params', 'is_public',
            'is_active', 'usage_count', 'last_used', 'created_at',
            'updated_at', 'created_by', 'created_by_name', 'updated_by',
            'updated_by_name', 'is_deleted', 'deleted_at', 'deleted_by'
        ]
        read_only_fields = [
            'id', 'usage_count', 'last_used', 'created_at', 'updated_at',
            'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
        ]
    
    def create(self, validated_data):
        """Set created_by when creating a new search query"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Set updated_by when updating a search query"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailReplySerializer(serializers.Serializer):
    """Serializer for replying to emails"""
    
    subject = serializers.CharField(max_length=500)
    html_content = serializers.CharField(required=False, allow_blank=True)
    text_content = serializers.CharField(required=False, allow_blank=True)
    to_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        help_text="Additional recipients"
    )
    cc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        default=list
    )
    bcc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        default=list
    )
    priority = serializers.ChoiceField(
        choices=EmailInboxMessage.PRIORITY_CHOICES,
        default='normal'
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )


class EmailForwardSerializer(serializers.Serializer):
    """Serializer for forwarding emails"""
    
    to_emails = serializers.ListField(
        child=serializers.EmailField(),
        help_text="Recipients to forward to"
    )
    cc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        default=list
    )
    bcc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        default=list
    )
    subject = serializers.CharField(max_length=500, required=False)
    message = serializers.CharField(required=False, allow_blank=True, help_text="Additional message")
    priority = serializers.ChoiceField(
        choices=EmailInboxMessage.PRIORITY_CHOICES,
        default='normal'
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )


class BulkEmailActionSerializer(serializers.Serializer):
    """Serializer for bulk email actions"""
    
    email_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of email IDs to perform action on"
    )
    action = serializers.ChoiceField(choices=[
        ('mark_resolved', 'Mark Resolved'),
        ('flag', 'Flag for Follow-Up'),
        ('unflag', 'Unflag'),
        ('assign_to', 'Bulk Assign'),
        ('mark_read', 'Mark as read'),
        ('mark_unread', 'Mark as unread'),
        ('star', 'Star'),
        ('unstar', 'Unstar'),
        ('mark_important', 'Mark as important'),
        ('unmark_important', 'Unmark important'),
        ('move_to_folder', 'Move to folder'),
        ('delete', 'Delete'),
        ('archive', 'Archive'),
        ('assign_to', 'Assign to user'),
        ('add_tag', 'Add tag'),
        ('remove_tag', 'Remove tag'),
    ])
    action_value = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text="Required only for 'assign_to' (User ID)"
    )


class EmailSearchSerializer(serializers.Serializer):
    """Serializer for email search"""
    
    query = serializers.CharField(required=False, allow_blank=True, help_text="Search query")
    folder_id = serializers.UUIDField(required=False, allow_null=True)
    category = serializers.ChoiceField(
        choices=EmailInboxMessage.CATEGORY_CHOICES,
        required=False
    )
    priority = serializers.ChoiceField(
        choices=EmailInboxMessage.PRIORITY_CHOICES,
        required=False
    )
    status = serializers.ChoiceField(
        choices=EmailInboxMessage.STATUS_CHOICES,
        required=False
    )
    sentiment = serializers.ChoiceField(
        choices=EmailInboxMessage.SENTIMENT_CHOICES,
        required=False
    )
    from_email = serializers.EmailField(required=False, allow_blank=True)
    to_emails = serializers.EmailField(required=False, allow_blank=True)
    assigned_to = serializers.UUIDField(required=False, allow_null=True)
    is_starred = serializers.BooleanField(required=False)
    is_important = serializers.BooleanField(required=False)
    has_attachments = serializers.BooleanField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    sort_by = serializers.ChoiceField(
        choices=[
            ('received_at', 'Received Date'),
            ('subject', 'Subject'),
            ('from_email', 'From'),
            ('priority', 'Priority'),
            ('category', 'Category'),
        ],
        default='received_at'
    )
    sort_order = serializers.ChoiceField(
        choices=[('asc', 'Ascending'), ('desc', 'Descending')],
        default='desc'
    )


class EmailStatisticsSerializer(serializers.Serializer):
    """Serializer for email statistics"""
    
    total_emails = serializers.IntegerField()
    unread_emails = serializers.IntegerField()
    read_emails = serializers.IntegerField()
    starred_emails = serializers.IntegerField()
    important_emails = serializers.IntegerField()
    emails_by_status = serializers.DictField()
    emails_by_category = serializers.DictField()
    emails_by_priority = serializers.DictField()
    emails_by_sentiment = serializers.DictField()
    emails_by_folder = serializers.DictField()
    recent_activity = serializers.ListField()
    top_senders = serializers.ListField()
    response_time_stats = serializers.DictField()
class EmailComposeSerializer(serializers.Serializer):
    """Serializer for composing and sending a new email"""
    to_emails = serializers.ListField(child=serializers.EmailField())
    cc_emails = serializers.ListField(child=serializers.EmailField(), required=False, default=list)
    bcc_emails = serializers.ListField(child=serializers.EmailField(), required=False, default=list)
    subject = serializers.CharField(max_length=500)
    html_content = serializers.CharField(required=False, allow_blank=True)
    text_content = serializers.CharField(required=False, allow_blank=True)
class EmailInboxListSerializer(serializers.ModelSerializer):
    # Only fields needed for the columns
    due_status = serializers.SerializerMethodField()
    date_column = serializers.SerializerMethodField()
    due_date_column = serializers.SerializerMethodField()
    from_display = serializers.SerializerMethodField()
    snippet = serializers.SerializerMethodField()
    has_attachments = serializers.SerializerMethodField()

    class Meta:
        model = EmailInboxMessage
        fields = [
            'id', 
            'message_id', 
            'is_starred',
            'from_display',
            'from_email',
            'subject',
            'snippet',          # Just a 1-line preview, NOT full body
            'customer_type',    # VIP/Normal badge
            'priority',
            'has_attachments',  # Just a boolean icon
            'status',
            'date_column',
            'due_date_column',
            'due_status',
        ]
    def get_has_attachments(self, obj):
        return obj.attachment_count > 0
    
    def get_snippet(self, obj):
        """Returns the first 100 characters of the email body, stripped of HTML."""
        # Get raw content
        body = obj.text_content or obj.html_content or ""
        
        # FIX: Remove HTML tags so it looks clean in the UI
        clean_body = strip_tags(body)
        
        # Remove extra whitespace/newlines
        clean_body = " ".join(clean_body.split())
        
        if len(clean_body) > 100:
            return clean_body[:100] + "..."
        return clean_body

    def get_due_status(self, obj):
        return "ON TRACK" 

    def get_date_column(self, obj):
        if not obj.received_at: return None
        return {
            "date": obj.received_at.strftime("%m/%d/%Y"),
            "time": obj.received_at.strftime("%I:%M %p")
        }

    def get_due_date_column(self, obj):
        return {"status": "No due date"}

    def get_from_display(self, obj):
        return obj.from_name if obj.from_name else obj.from_email

class EmailAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAttachment
        fields = ['id', 'filename', 'file_path', 'file_size', 'content_type']

class EmailInboxDetailSerializer(serializers.ModelSerializer):
    # Full details for the page view
    internal_notes = serializers.SerializerMethodField()
    attachments = EmailAttachmentSerializer(many=True, read_only=True)
    formatted_date = serializers.SerializerMethodField()
    thread_history = serializers.SerializerMethodField()

    class Meta:
        model = EmailInboxMessage
        fields = [
            'id',
            'message_id',
            'thread_id',
            'subject',
            'from_email',
            'from_name',
            'to_emails',
            'cc_emails',
            'bcc_emails',
            'received_at',
            'formatted_date',
            
            # Content
            'html_content',     
            'text_content',
            
            # Metadata
            'tags',            
            'customer_type',
            'priority',
            'status',
            'category',       # <--- Make sure this is here for the dropdown
            'folder',
            
            # Related Data
            'attachments',     
            'internal_notes',
            'thread_history'  # <--- Add this
        ]

    def get_formatted_date(self, obj):
        if not obj.received_at: return ""
        return obj.received_at.strftime("%B %d, %Y at %I:%M %p")

    def get_internal_notes(self, obj):
        return [{
            'id': note.id,
            'note': note.note,
            'author': note.author.get_full_name() if note.author else 'System',
            'created_at': note.created_at
        } for note in obj.internal_notes.all().order_by('-created_at')]

    def get_thread_history(self, obj):
        """
        Fetches other emails in the same conversation thread,
        excluding the current one being viewed.
        """
        if not obj.thread_id:
            return []

        # Find other messages with same thread_id
        threads = EmailInboxMessage.objects.filter(
            thread_id=obj.thread_id, 
            is_deleted=False
        ).exclude(id=obj.id).order_by('-received_at') 

        # Return a simplified list for the UI
        return [{
            'id': t.id,
            'subject': t.subject,
            'from_email': t.from_email,
            'snippet': (t.text_content or "")[:100] + "...", 
            'received_at': t.received_at,
            'formatted_date': t.received_at.strftime("%b %d, %I:%M %p") if t.received_at else "",
            'status': t.status
        } for t in threads]

class BulkEmailCampaignSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    template_id = serializers.UUIDField(write_only=True, required=False) 
    
    class Meta:
        model = BulkEmailCampaign
        fields = [
            'id', 
            'name', 
            'template_id',          # This input field causes the TypeError
            'subject_template', 
            'body_html_template',
            'custom_subject', 
            'additional_message',
            'recipients_data', 
            'scheduled_at', 
            'sent_at', 
            'status', 
            'total_recipients', 
            'successful_sends', 
            'failed_sends', 
            'created_by', 
            'created_by_name',
            'created_at', 
            'updated_at'
        ]
        read_only_fields = [
            'id', 'sent_at', 'status', 'total_recipients', 
            'successful_sends', 'failed_sends', 'created_by', 
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'subject_template': {'required': False},
            'body_html_template': {'required': False},
            'custom_subject': {'required': False},
            'additional_message': {'required': False},
            'recipients_data': {'required': True}
        }

    # --- FIX FOR TypeError: BulkEmailCampaign() got unexpected keyword arguments: 'template_id' ---
    def create(self, validated_data):
        # 1. Pop the non-model field from the dictionary
        template_id = validated_data.pop('template_id', None)
        
        # 2. Pop the calculated fields which might be None if user didn't input them 
        # (This avoids passing None to mandatory ModelFields, although your fields are now null=True)
        # We don't need this step as the content is populated in validate()

        # 3. Create the model instance using the remaining validated data
        return super().create(validated_data)

    def validate(self, data):
        # Your existing template lookup logic MUST remain here to populate subject/body
        template_id = data.get('template_id')
        
        if template_id:
            try:
                EmailTemplate = apps.get_model('email_templates', 'EmailTemplate')
                template = EmailTemplate.objects.get(id=template_id)
                
                if not data.get('subject_template'):
                    data['subject_template'] = template.subject
                
                if not data.get('body_html_template'):
                    data['body_html_template'] = getattr(template, 'body_html', getattr(template, 'html_content', ''))
                    
            except Exception as e:
                raise serializers.ValidationError(f"Invalid Template ID: {str(e)}")
        
        # Final Safety Check
        if not data.get('subject_template') or not data.get('body_html_template'):
             raise serializers.ValidationError("Template content missing.")

        # Validate schedule time
        from django.utils import timezone
        if data.get('scheduled_at') and data['scheduled_at'] < timezone.now():
             raise serializers.ValidationError({"scheduled_at": "Scheduled time cannot be in the past."})

        return data
class EmailAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for the Audit Trail history.
    """
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    subtitle = serializers.SerializerMethodField()

    class Meta:
        model = EmailAuditLog
        fields = ['id', 'action', 'details', 'performed_by_name', 'timestamp', 'subtitle']

    def get_subtitle(self, obj):
        name = obj.performed_by.get_full_name() if obj.performed_by else "System"
        time_diff = timesince(obj.timestamp).split(',')[0]
        
        return f"{name} • {time_diff} ago"
class RecipientImportSerializer(serializers.Serializer):
    """
    Handles the 'Bulk Import' modal data. 
    Accepts raw CSV text or a file and returns structured JSON.
    """
    # Option 1: Copy-pasted text from the modal
    csv_text = serializers.CharField(required=False, allow_blank=True, help_text="Raw text from the import modal")
    # Option 2: File upload
    file = serializers.FileField(required=False, help_text="CSV or Excel file")

    def validate(self, data):
        if not data.get('csv_text') and not data.get('file'):
            raise serializers.ValidationError("Please provide either text or a file.")
        return data