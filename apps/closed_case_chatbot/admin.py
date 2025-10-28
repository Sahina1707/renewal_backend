from django.contrib import admin
from .models import ClosedCaseChatbot, ClosedCaseChatbotMessage, ClosedCaseChatbotAnalytics


@admin.register(ClosedCaseChatbot)
class ClosedCaseChatbotAdmin(admin.ModelAdmin):
    list_display = [
        'case_id', 'customer_name', 'policy_number', 'product_name', 
        'category', 'mobile_number', 'language', 'profile_type',
        'interaction_count', 'is_active', 'created_at'
    ]
    list_filter = [
        'category', 'profile_type', 'language', 'is_active', 'created_at'
    ]
    search_fields = [
        'case_id', 'customer_name', 'policy_number', 'mobile_number'
    ]
    readonly_fields = ['created_at', 'updated_at', 'last_interaction']
    list_per_page = 25
    
    fieldsets = (
        ('Case Information', {
            'fields': ('case_id', 'customer_name', 'policy_number', 'product_name', 'category')
        }),
        ('Customer Details', {
            'fields': ('mobile_number', 'language', 'profile_type')
        }),
        ('Chatbot Settings', {
            'fields': ('chatbot_session_id', 'is_active', 'interaction_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_interaction'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ClosedCaseChatbotMessage)
class ClosedCaseChatbotMessageAdmin(admin.ModelAdmin):
    list_display = [
        'chatbot_session', 'message_type', 'content_preview', 
        'timestamp', 'is_helpful'
    ]
    list_filter = [
        'message_type', 'is_helpful', 'timestamp'
    ]
    search_fields = [
        'chatbot_session__case_id', 'chatbot_session__customer_name', 'content'
    ]
    readonly_fields = ['timestamp']
    list_per_page = 25
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(ClosedCaseChatbotAnalytics)
class ClosedCaseChatbotAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'chatbot_session', 'metric_name', 'metric_value', 'metric_date'
    ]
    list_filter = [
        'metric_name', 'metric_date'
    ]
    search_fields = [
        'chatbot_session__case_id', 'chatbot_session__customer_name', 'metric_name'
    ]
    list_per_page = 25
