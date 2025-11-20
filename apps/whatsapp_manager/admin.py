from django.contrib import admin
from .models import WhatsAppMessage

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['case', 'sender_type', 'content', 'created_at', 'is_read']
    list_filter = ['sender_type', 'message_type', 'is_read']
    search_fields = ['case__case_number', 'content']
    ordering = ['-created_at']