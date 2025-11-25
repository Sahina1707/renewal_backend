from rest_framework import serializers
from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery
    
)


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
            'color', 'is_system', 'is_active'
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
            'id', 'is_system', 'match_count', 'last_matched', 'created_at',
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
        help_text="Action parameter (folder ID, user ID, tag name, etc.)"
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