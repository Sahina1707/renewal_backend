from django.contrib import admin
from .models import EmailManager


@admin.register(EmailManager)
class EmailManagerAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'to',
        'subject',
        'policy_number',
        'customer_name',
        'priority',
        'email_status',
        'schedule_send',
        'schedule_date_time',
        'sent_at',
        'track_opens',
        'track_clicks',
        'created_at',
    ]
    list_filter = [
        'priority',
        'email_status',
        'schedule_send',
        'track_opens',
        'track_clicks',
        'created_at',
    ]
    search_fields = [
        'to',
        'cc',
        'bcc',
        'subject',
        'policy_number',
        'customer_name',
    ]
    readonly_fields = ['created_at', 'updated_at', 'email_status', 'sent_at', 'error_message']
    date_hierarchy = 'created_at'

