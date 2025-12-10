from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import EmailProviderConfig, EmailProviderHealthLog, EmailProviderUsageLog, EmailProviderTestResult


@admin.register(EmailProviderConfig)
class EmailProviderConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'provider_type', 'from_email', 'priority', 'is_active',
        'health_status', 'emails_sent_today', 'emails_sent_this_month',
        'daily_usage_percentage', 'monthly_usage_percentage', 'last_health_check'
    ]
    list_filter = [
        'provider_type', 'is_active', 'health_status', 'priority',
        'is_default', 'created_at'
    ]
    search_fields = ['name', 'from_email', 'from_name']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
        'last_health_check', 'emails_sent_today', 'emails_sent_this_month',
        'last_reset_daily', 'last_reset_monthly', 'is_deleted', 'deleted_at', 'deleted_by'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider_type', 'priority', 'is_default', 'is_active')
        }),
        ('Email Settings', {
            'fields': ('from_email', 'from_name', 'reply_to')
        }),
        ('SendGrid Configuration', {
            'fields': ('api_key', 'api_secret'),
            'classes': ('collapse',)
        }),
        ('AWS SES Configuration', {
            'fields': ('access_key_id', 'secret_access_key'),
            'classes': ('collapse',)
        }),
        ('SMTP Configuration', {
            'fields': (
                'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
                'smtp_use_tls', 'smtp_use_ssl'
            ),
            'classes': ('collapse',)
        }),
        ('Rate Limiting', {
            'fields': ('daily_limit', 'monthly_limit', 'rate_limit_per_minute')
        }),
        ('Health Monitoring', {
            'fields': ('health_status', 'last_health_check')
        }),
        ('Usage Tracking', {
            'fields': ('emails_sent_today', 'emails_sent_this_month', 'last_reset_daily', 'last_reset_monthly')
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
    
    def daily_usage_percentage(self, obj):
        sent = obj.emails_sent_today or 0
        limit = obj.daily_limit or 0

        if limit == 0:
            return "N/A (No Limit)"

        percent_val = (sent / limit) * 100

    # Compute colour coding
        if percent_val > 90:
            color = "red"
        elif percent_val > 75:
            color = "orange"
        else:
            color = "green"

    # Format BEFORE passing to format_html
        percent_val = f"{percent_val:.1f}%"

        return format_html(
        '<span style="color: {}; font-weight: bold;">{}</span>',
        color,
        percent_val
    )
        
    
    def monthly_usage_percentage(self, obj):
        # 1. Get raw values safely
        sent = obj.emails_sent_this_month or 0
        limit = obj.monthly_limit or 0
        
        # 2. Prevent Division by Zero
        if limit == 0:
            return "N/A (No Limit)"
            
        # 3. Calculate percentage
        try:
            percent_val = (float(sent) / float(limit)) * 100
        except (ValueError, TypeError):
            return "Error"

        # 4. Determine color
        if percent_val > 90:
            color = 'red'
        elif percent_val > 75:
            color = 'orange'
        else:
            color = 'green'

        # 5. Return formatted HTML
        from django.utils.html import format_html
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, 
            round(percent_val, 1)  # Using round() prevents the string formatting crash
        )
    
    monthly_usage_percentage.short_description = "Monthly Usage"
    def get_queryset(self, request):
        """Filter out soft-deleted providers"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_providers', 'deactivate_providers', 'reset_daily_usage', 'reset_monthly_usage']
    
    def activate_providers(self, request, queryset):
        """Activate selected providers"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} providers activated successfully.")
    activate_providers.short_description = "Activate selected providers"
    
    def deactivate_providers(self, request, queryset):
        """Deactivate selected providers"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} providers deactivated successfully.")
    deactivate_providers.short_description = "Deactivate selected providers"
    
    def reset_daily_usage(self, request, queryset):
        """Reset daily usage for selected providers"""
        for provider in queryset:
            provider.reset_daily_usage()
        self.message_user(request, f"Daily usage reset for {queryset.count()} providers.")
    reset_daily_usage.short_description = "Reset daily usage"
    
    def reset_monthly_usage(self, request, queryset):
        """Reset monthly usage for selected providers"""
        for provider in queryset:
            provider.reset_monthly_usage()
        self.message_user(request, f"Monthly usage reset for {queryset.count()} providers.")
    reset_monthly_usage.short_description = "Reset monthly usage"


@admin.register(EmailProviderHealthLog)
class EmailProviderHealthLogAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'is_healthy', 'response_time', 'checked_at'
    ]
    list_filter = ['is_healthy', 'provider', 'checked_at']
    search_fields = ['provider__name',
                    #   'error_message'
                      ]
    readonly_fields = ['id', 'checked_at']
    date_hierarchy = 'checked_at'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('provider')


@admin.register(EmailProviderUsageLog)
class EmailProviderUsageLogAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'emails_sent', 'success_count', 'failure_count',
        'success_rate', 'average_response_time', 'logged_at'
    ]
    list_filter = ['provider', 'logged_at']
    search_fields = ['provider__name']
    readonly_fields = ['id', 'logged_at']
    date_hierarchy = 'logged_at'
    
    def success_rate(self, obj):
        """Calculate success rate"""
        if obj.emails_sent == 0:
            return "N/A"
        rate = (obj.success_count / obj.emails_sent) * 100
        color = "red" if rate < 80 else "orange" if rate < 95 else "green"
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    success_rate.short_description = "Success Rate"
    
    def average_response_time(self, obj):
        """Calculate average response time"""
        if obj.success_count == 0:
            return "N/A"
        avg_time = obj.total_response_time / obj.success_count
        return f"{avg_time:.3f}s"
    average_response_time.short_description = "Avg Response Time"
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('provider')


@admin.register(EmailProviderTestResult)
class EmailProviderTestResultAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 
        'test_email', 
        'status', 
        'response_time', 
        'tested_at', 
        'tested_by'
    ]
    list_filter = ['status', 'provider', 'tested_at']
    search_fields = ['provider__name', 'test_email', 'tested_by__username']
    readonly_fields = ['id', 'tested_at']
    date_hierarchy = 'tested_at'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('provider', 'tested_by')
