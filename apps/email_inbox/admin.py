from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery
)


@admin.register(EmailFolder)
class EmailFolderAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'folder_type', 'is_system', 'is_active',
        'message_count', 'unread_count', 'created_at'
    ]
    list_filter = ['folder_type', 'is_system', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def message_count(self, obj):
        """Count of messages in this folder"""
        return obj.messages.filter(is_deleted=False).count()
    message_count.short_description = 'Messages'
    
    def unread_count(self, obj):
        """Count of unread messages in this folder"""
        return obj.messages.filter(is_deleted=False, status='unread').count()
    unread_count.short_description = 'Unread'
    
    def get_queryset(self, request):
        """Filter out soft-deleted folders"""
        return super().get_queryset(request).filter(is_deleted=False)


@admin.register(EmailInboxMessage)
class EmailInboxMessageAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'from_email', 'to_emails_display', 'category', 'priority',
        'status', 'is_starred', 'is_important', 'received_at'
    ]
    list_filter = [
        'category', 'priority', 'status', 'sentiment', 'is_starred',
        'is_important', 'received_at', 'created_at'
    ]
    search_fields = ['subject', 'from_email', 'message_id']
    readonly_fields = [
        'id', 'message_id', 'received_at', 'read_at', 'replied_at',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('subject', 'from_email', 'from_name', 'to_emails', 'cc_emails', 'bcc_emails', 'reply_to')
        }),
        ('Content', {
            'fields': ('html_content', 'text_content', 'raw_headers', 'raw_body')
        }),
        ('Classification', {
            'fields': ('category', 'priority', 'sentiment', 'status')
        }),
        ('Organization', {
            'fields': ('folder', 'is_starred', 'is_important', 'tags', 'thread_id',
                        'parent_message')
        }),
        ('Processing', {
            'fields': ('is_processed', 'processing_notes', 'assigned_to')
        }),
        ('Timestamps', {
            'fields': ('received_at', 'read_at', 'replied_at', 'forwarded_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'message_id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',)
        })
    )
    
    def to_emails_display(self, obj):
        """Display to_emails as a comma-separated list"""
        if obj.to_emails:
            return ', '.join(obj.to_emails[:3]) + ('...' if len(obj.to_emails) > 3 else '')
        return '-'
    to_emails_display.short_description = 'To'
    
    def get_queryset(self, request):
        """Filter out soft-deleted messages"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['mark_as_read', 'mark_as_unread', 'star_emails', 'unstar_emails', 'archive_emails']
    
    def mark_as_read(self, request, queryset):
        """Mark selected emails as read"""
        count = queryset.filter(status='unread').update(status='read', read_at=timezone.now())
        self.message_user(request, f"{count} emails marked as read.")
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_unread(self, request, queryset):
        """Mark selected emails as unread"""
        count = queryset.update(status='unread', read_at=None)
        self.message_user(request, f"{count} emails marked as unread.")
    mark_as_unread.short_description = "Mark as unread"
    
    def star_emails(self, request, queryset):
        """Star selected emails"""
        count = queryset.update(is_starred=True)
        self.message_user(request, f"{count} emails starred.")
    star_emails.short_description = "Star emails"
    
    def unstar_emails(self, request, queryset):
        """Unstar selected emails"""
        count = queryset.update(is_starred=False)
        self.message_user(request, f"{count} emails unstarred.")
    unstar_emails.short_description = "Unstar emails"
    
    def archive_emails(self, request, queryset):
        """Archive selected emails"""
        count = queryset.update(status='archived')
        self.message_user(request, f"{count} emails archived.")
    archive_emails.short_description = "Archive emails"


@admin.register(EmailConversation)
class EmailConversationAdmin(admin.ModelAdmin):
    list_display = [
        'thread_id', 'subject', 'participants_display', 'message_count',
        'unread_count', 'last_message_at', 'last_message_from'
    ]
    list_filter = ['last_message_at', 'created_at']
    search_fields = ['thread_id', 'subject', 'participants']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def participants_display(self, obj):
        """Display participants as a comma-separated list"""
        return ', '.join(obj.participants[:3]) + ('...' if len(obj.participants) > 3 else '')
    participants_display.short_description = 'Participants'


@admin.register(EmailFilter)
class EmailFilterAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'filter_type', 'operator', 'value', 'action', 'action_value',
        'is_active', 'is_system', 'priority', 'match_count', 'last_matched'
    ]
    list_filter = ['filter_type', 'operator', 'action', 'is_active', 'is_system', 'created_at']
    search_fields = ['name', 'description', 'value', 'action_value']
    readonly_fields = ['id', 'match_count', 'last_matched', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active', 'is_system', 'priority')
        }),
        ('Filter Conditions', {
            'fields': ('filter_type', 'operator', 'value')
        }),
        ('Actions', {
            'fields': ('action', 'action_value')
        }),
        ('Statistics', {
            'fields': ('match_count', 'last_matched'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Filter out soft-deleted filters"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_filters', 'deactivate_filters']
    
    def activate_filters(self, request, queryset):
        """Activate selected filters"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} filters activated.")
    activate_filters.short_description = "Activate selected filters"
    
    def deactivate_filters(self, request, queryset):
        """Deactivate selected filters"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} filters deactivated.")
    deactivate_filters.short_description = "Deactivate selected filters"


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'email_message_subject', 'content_type', 'file_size_display',
        'is_safe', 'created_at'
    ]
    list_filter = ['content_type', 'is_safe', 'created_at']
    search_fields = ['filename', 'email_message__subject', 'email_message__from_email']
    readonly_fields = ['id', 'file_size', 'is_safe', 'scan_result', 'created_at', 'created_by']
    
    def email_message_subject(self, obj):
        """Display email message subject"""
        return obj.email_message.subject
    email_message_subject.short_description = 'Email Subject'
    
    def file_size_display(self, obj):
        """Format file size for display"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = 'File Size'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('email_message', 'created_by')


@admin.register(EmailSearchQuery)
class EmailSearchQueryAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'is_public', 'is_active', 'usage_count', 'last_used',
        'created_by', 'created_at'
    ]
    list_filter = ['is_public', 'is_active', 'created_at', 'last_used']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['id', 'usage_count', 'last_used', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_public', 'is_active')
        }),
        ('Search Parameters', {
            'fields': ('query_params',)
        }),
        ('Usage Statistics', {
            'fields': ('usage_count', 'last_used'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Filter out soft-deleted search queries"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_queries', 'deactivate_queries']
    
    def activate_queries(self, request, queryset):
        """Activate selected search queries"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} search queries activated.")
    activate_queries.short_description = "Activate selected queries"
    
    def deactivate_queries(self, request, queryset):
        """Deactivate selected search queries"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} search queries deactivated.")
    deactivate_queries.short_description = "Deactivate selected queries"
