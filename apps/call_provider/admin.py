from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CallProviderConfig,
    CallProviderHealthLog,
    CallProviderUsageLog,
    CallProviderTestResult,
)


@admin.register(CallProviderConfig)
class CallProviderConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'provider_type', 'priority', 'is_active',
        'status', 'calls_made_today', 'calls_made_this_month',
        'daily_usage_percentage', 'monthly_usage_percentage',
        'last_health_check',
    ]
    list_filter = [
        'provider_type', 'is_active', 'status', 'priority',
        'is_default', 'created_at',
    ]
    search_fields = ['name']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
        'last_health_check', 'calls_made_today', 'calls_made_this_month',
        'last_reset_daily', 'last_reset_monthly',
        'is_deleted', 'deleted_at', 'deleted_by',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider_type', 'priority', 'is_default', 'is_active')
        }),

        # TWILIO
        ('Twilio Configuration', {
            'fields': (
                'twilio_account_sid',
                'twilio_auth_token',
                'twilio_from_number',
                'twilio_status_callback_url',
                'twilio_voice_url',
            ),
            'classes': ('collapse',),
        }),

        # EXOTEL
        ('Exotel Configuration', {
            'fields': (
                'exotel_api_key',
                'exotel_api_token',
                'exotel_account_sid',
                'exotel_subdomain',
                'exotel_caller_id',
            ),
            'classes': ('collapse',),
        }),

        # UBONA
        ('Ubona Configuration', {
            'fields': (
                'ubona_api_key',
                'ubona_api_url',
                'ubona_account_sid',
                'ubona_caller_id',
            ),
            'classes': ('collapse',),
        }),

        ('Rate Limiting', {
            'fields': ('daily_limit', 'monthly_limit', 'rate_limit_per_minute'),
        }),

        ('Connection Status', {
            'fields': ('status', 'last_health_check'),
        }),

        ('Usage Tracking', {
            'fields': (
                'calls_made_today',
                'calls_made_this_month',
                'last_reset_daily',
                'last_reset_monthly',
            ),
        }),

        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),

        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    # ---------- custom columns ----------

    def daily_usage_percentage(self, obj):
        """Daily calls usage % (coloured like email admin)."""
        if obj.daily_limit == 0:
            return "N/A"
        percentage = (obj.calls_made_today / obj.daily_limit) * 100
        color = "red" if percentage > 80 else "orange" if percentage > 60 else "green"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)

    daily_usage_percentage.short_description = "Daily Usage %"

    def monthly_usage_percentage(self, obj):
        """Monthly calls usage %."""
        if obj.monthly_limit == 0:
            return "N/A"
        percentage = (obj.calls_made_this_month / obj.monthly_limit) * 100
        color = "red" if percentage > 80 else "orange" if percentage > 60 else "green"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)

    monthly_usage_percentage.short_description = "Monthly Usage %"

    def get_queryset(self, request):
        """Hide soft-deleted call providers."""
        return super().get_queryset(request).filter(is_deleted=False)

    # ---------- bulk actions ----------

    actions = ['activate_providers', 'deactivate_providers',
               'reset_daily_usage', 'reset_monthly_usage']

    def activate_providers(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} call providers activated successfully.")

    activate_providers.short_description = "Activate selected call providers"

    def deactivate_providers(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} call providers deactivated successfully.")

    deactivate_providers.short_description = "Deactivate selected call providers"

    def reset_daily_usage(self, request, queryset):
        for provider in queryset:
            provider.reset_daily_usage()
        self.message_user(request, f"Daily usage reset for {queryset.count()} call providers.")

    reset_daily_usage.short_description = "Reset daily usage"

    def reset_monthly_usage(self, request, queryset):
        for provider in queryset:
            provider.reset_monthly_usage()
        self.message_user(request, f"Monthly usage reset for {queryset.count()} call providers.")

    reset_monthly_usage.short_description = "Reset monthly usage"


@admin.register(CallProviderHealthLog)
class CallProviderHealthLogAdmin(admin.ModelAdmin):
    # 🔽 changed is_connected → is_healthy
    list_display = ['provider', 'is_healthy', 'response_time', 'checked_at']
    list_filter = ['is_healthy', 'provider', 'checked_at']
    search_fields = ['provider__name', 'error_message']
    readonly_fields = ['id', 'checked_at']
    date_hierarchy = 'checked_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider')


@admin.register(CallProviderUsageLog)
class CallProviderUsageLogAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'calls_made', 'success_count', 'failure_count',
        'success_rate', 'average_response_time', 'logged_at',
    ]
    list_filter = ['provider', 'logged_at']
    search_fields = ['provider__name']
    readonly_fields = ['id', 'logged_at']
    date_hierarchy = 'logged_at'

    def success_rate(self, obj):
        if obj.calls_made == 0:
            return "N/A"
        rate = (obj.success_count / obj.calls_made) * 100
        color = "red" if rate < 80 else "orange" if rate < 95 else "green"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    success_rate.short_description = "Success Rate"

    def average_response_time(self, obj):
        if obj.success_count == 0:
            return "N/A"
        avg_time = obj.total_response_time / obj.success_count
        return f"{avg_time:.3f}s"

    average_response_time.short_description = "Avg Response Time"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider')


@admin.register(CallProviderTestResult)
class CallProviderTestResultAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'test_number', 'status',
        'response_time', 'tested_at', 'tested_by',
    ]
    list_filter = ['status', 'provider', 'tested_at']
    search_fields = ['provider__name', 'test_number', 'tested_by__username']
    readonly_fields = ['id', 'tested_at']
    date_hierarchy = 'tested_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider', 'tested_by')
