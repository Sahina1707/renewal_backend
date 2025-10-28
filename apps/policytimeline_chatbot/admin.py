from django.contrib import admin
from .models import PolicyTimelineChatbot, PolicyTimelineChatbotMessage


@admin.register(PolicyTimelineChatbot)
class PolicyTimelineChatbotAdmin(admin.ModelAdmin):
    list_display = [
        'customer_id', 'customer_name', 'policy_id', 'policy_type', 
        'policy_premium', 'policy_age', 'interaction_count', 'is_active', 'created_at'
    ]
    list_filter = [
        'policy_type', 'is_active', 'created_at'
    ]
    search_fields = [
        'customer_id', 'customer_name', 'policy_id'
    ]
    readonly_fields = ['created_at', 'updated_at', 'last_interaction']
    list_per_page = 25
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer_id', 'customer_name')
        }),
        ('Policy Details', {
            'fields': ('policy_id', 'policy_type', 'policy_premium', 'policy_start_date', 'policy_age')
        }),
        ('Chatbot Settings', {
            'fields': ('chatbot_session_id', 'is_active', 'interaction_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_interaction'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PolicyTimelineChatbotMessage)
class PolicyTimelineChatbotMessageAdmin(admin.ModelAdmin):
    list_display = [
        'chatbot_session', 'message_type', 'content_preview', 
        'timestamp', 'is_helpful'
    ]
    list_filter = [
        'message_type', 'is_helpful', 'timestamp'
    ]
    search_fields = [
        'chatbot_session__customer_id', 'chatbot_session__customer_name', 'content'
    ]
    readonly_fields = ['timestamp']
    list_per_page = 25
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'
