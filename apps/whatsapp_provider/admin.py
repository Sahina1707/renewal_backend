from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    WhatsAppProvider, # Renamed
    WhatsAppPhoneNumber,
    WhatsAppMessageTemplate,
    WhatsAppMessage,
    WhatsAppWebhookEvent,
    WhatsAppFlow,
    WhatsAppAccountHealthLog,
    WhatsAppAccountUsageLog,
)


@admin.register(WhatsAppProvider)
class WhatsAppProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider_type', 'status', 'is_active', 'created_at']
    list_filter = ['provider_type', 'status', 'is_active']
    
    fieldsets = (
        ('General Info', {
            'fields': ('name', 'provider_type', 'status', 'is_default', 'is_active')
        }),
        ('Credentials', {
            'fields': ('access_token', 'account_id', 'phone_number_id', 'app_id'),
            'description': 'Enter credentials corresponding to the selected provider type.'
        }),
        ('Advanced Config', {
            'fields': ('api_version', 'api_url', 'webhook_verify_token'),
            'classes': ('collapse',)
        }),
        ('Business Profile', {
            'fields': ('business_name', 'business_email', 'business_description')
        }),
        ('Bot Config', {
            'fields': ('enable_auto_reply', 'greeting_message')
        })
    )
@admin.register(WhatsAppPhoneNumber)
class WhatsAppPhoneNumberAdmin(admin.ModelAdmin):
    list_display = [
        'display_phone_number', 'provider', 'status', 'is_primary',
        'quality_rating', 'messages_sent_today', 'created_at'
    ]
    list_filter = [
        'status', 'is_primary', 'is_active', 'quality_rating',
        'provider', 'created_at'
    ]
    search_fields = [
        'phone_number', 'display_phone_number', 'phone_number_id',
        'provider__name'
    ]
    readonly_fields = [
        'phone_number_id', 'messages_sent_today', 'messages_sent_this_month',
        'created_at', 'updated_at', 'verified_at'
    ]
    
    fieldsets = (
        ('Phone Number Details', {
            'fields': (
                'provider', 'phone_number_id', 'phone_number',
                'display_phone_number'
            )
        }),
        ('Status & Configuration', {
            'fields': ('status', 'is_primary', 'is_active', 'quality_rating')
        }),
        ('Usage Tracking', {
            'fields': ('messages_sent_today', 'messages_sent_this_month', 'last_message_sent')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'verified_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider')


@admin.register(WhatsAppMessageTemplate)
class WhatsAppMessageTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'provider', 'category', 'language', 'status',
        'usage_count', 'created_at'
    ]
    list_filter = [
        'status', 'category', 'language', 'provider', 'created_at'
    ]
    search_fields = [
        'name', 'body_text', 'provider__name', 'meta_template_id'
    ]
    readonly_fields = [
        'meta_template_id', 'usage_count', 'last_used', 'created_at',
        'updated_at', 'approved_at'
    ]
    
    fieldsets = (
        ('Template Information', {
            'fields': ('provider', 'name', 'category', 'language')
        }),
        ('Template Content', {
            'fields': ('header_text', 'body_text', 'footer_text', 'components')
        }),
        ('Approval Status', {
            'fields': ('status', 'meta_template_id', 'rejection_reason')
        }),
        ('Usage Tracking', {
            'fields': ('usage_count', 'last_used')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'approved_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider', 'created_by')


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = [
        'message_id', 'direction', 'message_type', 'to_phone_number',
        'status', 'created_at', 'provider'
    ]
    list_filter = [
        'direction', 'message_type', 'status', 'provider',
        'phone_number', 'created_at'
    ]
    search_fields = [
        'message_id', 'to_phone_number', 'from_phone_number',
        'provider__name', 'customer__first_name', 'customer__last_name'
    ]
    readonly_fields = [
        'message_id', 'created_at', 'sent_at', 'delivered_at', 'read_at'
    ]
    
    fieldsets = (
        ('Message Details', {
            'fields': (
                'message_id', 'direction', 'message_type', 'provider',
                'phone_number', 'template'
            )
        }),
        ('Recipients', {
            'fields': ('to_phone_number', 'from_phone_number')
        }),
        ('Content', {
            'fields': ('content', 'metadata')
        }),
        ('Status & Delivery', {
            'fields': ('status', 'error_code', 'error_message')
        }),
        ('Context', {
            'fields': ('campaign', 'customer')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at', 'delivered_at', 'read_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'provider', 'phone_number', 'template', 'campaign', 'customer'
        )


@admin.register(WhatsAppWebhookEvent)
class WhatsAppWebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'provider', 'processed', 'received_at'
    ]
    list_filter = [
        'event_type', 'processed', 'provider', 'received_at'
    ]
    search_fields = [
        'provider__name', 'event_type', 'processing_error'
    ]
    readonly_fields = [
        'received_at', 'processed_at'
    ]
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_type', 'provider', 'message')
        }),
        ('Processing Status', {
            'fields': ('processed', 'processing_error', 'processed_at')
        }),
        ('Raw Data', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('received_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider', 'message')


@admin.register(WhatsAppFlow)
class WhatsAppFlowAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'provider', 'status', 'is_active', 'usage_count', 'created_at'
    ]
    list_filter = [
        'status', 'is_active', 'provider', 'created_at'
    ]
    search_fields = [
        'name', 'description', 'provider__name'
    ]
    readonly_fields = [
        'usage_count', 'last_used', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Flow Information', {
            'fields': ('provider', 'name', 'description')
        }),
        ('Flow Configuration', {
            'fields': ('flow_json', 'status', 'is_active')
        }),
        ('Usage Tracking', {
            'fields': ('usage_count', 'last_used')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider', 'created_by')


@admin.register(WhatsAppAccountHealthLog)
class WhatsAppAccountHealthLogAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'health_status', 'checked_at'
    ]
    list_filter = [
        'health_status', 'provider', 'checked_at'
    ]
    search_fields = [
        'provider__name', 'error_message'
    ]
    readonly_fields = ['checked_at']
    
    fieldsets = (
        ('Health Check', {
            'fields': ('provider', 'health_status', 'error_message')
        }),
        ('Check Details', {
            'fields': ('check_details',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('checked_at',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider')


@admin.register(WhatsAppAccountUsageLog)
class WhatsAppAccountUsageLogAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'date', 'messages_sent', 'messages_delivered',
        'messages_failed', 'messages_read'
    ]
    list_filter = [
        'provider', 'date', 'created_at'
    ]
    search_fields = ['provider__name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Usage Information', {
            'fields': ('provider', 'date')
        }),
        ('Message Statistics', {
            'fields': (
                'messages_sent', 'messages_delivered', 'messages_failed', 'messages_read'
            )
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider')