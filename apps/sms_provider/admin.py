from django.contrib import admin
from .models import SmsProvider, SmsMessage

@admin.register(SmsProvider)
class SmsProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'status', 'is_default', 'is_active', 'rate_limit_per_minute', 'messages_sent_total')
    list_filter = ('provider_type', 'status', 'is_active', 'is_default')
    search_fields = ('name',)
    readonly_fields = ('messages_sent_today', 'messages_sent_total', 'last_sent_at', 'created_at', 'updated_at')
    fieldsets = (
        ('Provider Details', {
            'fields': ('name', 'provider_type', 'status', 'is_active', 'is_default')
        }),
        ('Credentials (Handled by API)', {
            'fields': ('credentials',),
            'classes': ('collapse',)
        }),
        ('Rate Limits', {
            'fields': ('rate_limit_per_minute', 'daily_limit', 'monthly_limit')
        }),
        ('Usage', {
            'fields': ('messages_sent_today', 'messages_sent_total', 'last_sent_at')
        }),
    )

@admin.register(SmsMessage)
class SmsMessageAdmin(admin.ModelAdmin):
    list_display = ('to_phone_number', 'provider', 'status', 'sent_at', 'message_sid')
    list_filter = ('status', 'provider', 'sent_at')
    search_fields = ('to_phone_number', 'message_sid', 'content')
    readonly_fields = ('created_at', 'sent_at', 'delivered_at')
