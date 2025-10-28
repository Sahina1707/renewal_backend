from django.contrib import admin
from .models import CaseLogsChatbot, CaseLogsChatbotMessage


@admin.register(CaseLogsChatbot)
class CaseLogsChatbotAdmin(admin.ModelAdmin):
    list_display = [
        'case_id', 'policy_id', 'customer_id', 'case_type', 
        'case_status', 'priority', 'interaction_count', 'is_active', 'created_at'
    ]
    list_filter = [
        'case_type', 'case_status', 'priority', 'is_active', 'created_at'
    ]
    search_fields = [
        'case_id', 'policy_id', 'customer_id'
    ]
    readonly_fields = ['created_at', 'updated_at', 'last_interaction']
    list_per_page = 25
    
    fieldsets = (
        ('Case Information', {
            'fields': ('case_id', 'policy_id', 'customer_id')
        }),
        ('Case Details', {
            'fields': ('case_type', 'case_status', 'priority')
        }),
        ('Chatbot Settings', {
            'fields': ('chatbot_session_id', 'is_active', 'interaction_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_interaction'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CaseLogsChatbotMessage)
class CaseLogsChatbotMessageAdmin(admin.ModelAdmin):
    list_display = [
        'chatbot_session', 'message_type', 'content_preview', 
        'timestamp', 'is_helpful'
    ]
    list_filter = [
        'message_type', 'is_helpful', 'timestamp'
    ]
    search_fields = [
        'chatbot_session__case_id', 'chatbot_session__policy_id', 'content'
    ]
    readonly_fields = ['timestamp']
    list_per_page = 25
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'
