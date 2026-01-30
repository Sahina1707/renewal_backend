from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    EmailWebhook, EmailAutomation, EmailAutomationLog, EmailIntegration,
    EmailSLA, EmailTemplateVariable, EmailIntegrationAnalytics
)


@admin.register(EmailWebhook)
class EmailWebhookAdmin(admin.ModelAdmin):
    list_display = [
        'provider', 'event_type', 'status', 'email_message_id',
        'created_at', 'processed_at'
    ]
    list_filter = ['provider', 'event_type', 'status', 'created_at']
    search_fields = ['email_message_id', 'provider_message_id', 'ip_address']
    readonly_fields = [
        'id', 'raw_data', 'processed_data', 'created_at', 'processed_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('provider', 'event_type', 'status', 'email_message_id', 'provider_message_id')
        }),
        ('Event Details', {
            'fields': ('event_time', 'ip_address', 'user_agent')
        }),
        ('Processing', {
            'fields': ('processing_notes', 'error_message', 'retry_count')
        }),
        ('Data', {
            'fields': ('raw_data', 'processed_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'processed_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['process_webhooks', 'mark_as_processed']
    
    def process_webhooks(self, request, queryset):
        """Process selected webhooks"""
        count = 0
        for webhook in queryset.filter(status='pending'):
            webhook.status = 'processed'
            webhook.save()
            count += 1
        
        self.message_user(request, f"{count} webhooks processed.")
    process_webhooks.short_description = "Process selected webhooks"
    
    def mark_as_processed(self, request, queryset):
        """Mark selected webhooks as processed"""
        count = queryset.update(status='processed')
        self.message_user(request, f"{count} webhooks marked as processed.")
    mark_as_processed.short_description = "Mark as processed"


@admin.register(EmailAutomation)
class EmailAutomationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'trigger_type', 'action_type', 'status', 'is_active',
        'execution_count', 'last_executed', 'created_at'
    ]
    list_filter = ['trigger_type', 'action_type', 'status', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'id', 'execution_count', 'last_executed', 'created_at', 'updated_at',
        'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'status', 'is_active', 'priority')
        }),
        ('Trigger Configuration', {
            'fields': ('trigger_type', 'trigger_conditions')
        }),
        ('Action Configuration', {
            'fields': ('action_type', 'action_config')
        }),
        ('Execution Settings', {
            'fields': ('max_executions', 'execution_count', 'last_executed', 'delay_seconds', 'cooldown_seconds')
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
        """Filter out soft-deleted automations"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_automations', 'deactivate_automations']
    
    def activate_automations(self, request, queryset):
        """Activate selected automations"""
        count = queryset.update(status='active', is_active=True)
        self.message_user(request, f"{count} automations activated.")
    activate_automations.short_description = "Activate selected automations"
    
    def deactivate_automations(self, request, queryset):
        """Deactivate selected automations"""
        count = queryset.update(status='inactive', is_active=False)
        self.message_user(request, f"{count} automations deactivated.")
    deactivate_automations.short_description = "Deactivate selected automations"

@admin.register(EmailAutomationLog)
class EmailAutomationLogAdmin(admin.ModelAdmin):
    list_display = [
        'automation_name', 'status', 'started_at', 'completed_at',
        'duration_seconds', 'created_at'
    ]
    list_filter = ['status', 'automation', 'created_at']
    search_fields = ['automation__name', 'error_message']
    readonly_fields = [
        'id', 'started_at', 'completed_at', 'duration_seconds', 'created_at'
    ]
    
    def automation_name(self, obj):
        """Display automation name"""
        return obj.automation.name
    automation_name.short_description = 'Automation'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('automation', 'executed_by')

@admin.register(EmailIntegration)
class EmailIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'integration_type', 'status', 'last_sync',
        'error_count', 'sync_enabled', 'created_at'
    ]
    list_filter = ['integration_type', 'status', 'sync_enabled', 'auto_sync', 'created_at']
    search_fields = ['name', 'description', 'api_endpoint']
    readonly_fields = [
        'id', 'last_sync', 'last_error', 'error_count', 'created_at',
        'updated_at', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'integration_type', 'description', 'status')
        }),
        ('API Configuration', {
            'fields': ('api_endpoint', 'api_key', 'api_secret', 'configuration')
        }),
        ('Sync Settings', {
            'fields': ('sync_enabled', 'sync_interval', 'auto_sync')
        }),
        ('Status and Health', {
            'fields': ('last_sync', 'last_error', 'error_count')
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
        """Filter out soft-deleted integrations"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['sync_integrations', 'activate_integrations', 'deactivate_integrations']
    
    def sync_integrations(self, request, queryset):
        """Sync selected integrations"""
        count = 0
        for integration in queryset.filter(sync_enabled=True):
            integration.last_sync = timezone.now()
            integration.save()
            count += 1
        
        self.message_user(request, f"{count} integrations synced.")
    sync_integrations.short_description = "Sync selected integrations"
    
    def activate_integrations(self, request, queryset):
        """Activate selected integrations"""
        count = queryset.update(status='active')
        self.message_user(request, f"{count} integrations activated.")
    activate_integrations.short_description = "Activate selected integrations"
    
    def deactivate_integrations(self, request, queryset):
        """Deactivate selected integrations"""
        count = queryset.update(status='inactive')
        self.message_user(request, f"{count} integrations deactivated.")
    deactivate_integrations.short_description = "Deactivate selected integrations"


@admin.register(EmailSLA)
class EmailSLAAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'sla_type', 'priority', 'target_value', 'warning_threshold',
        'is_active', 'total_incidents', 'met_sla_count', 'breached_sla_count'
    ]
    list_filter = ['sla_type', 'priority', 'is_active', 'is_escalation_enabled', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'id', 'total_incidents', 'met_sla_count', 'breached_sla_count',
        'warning_count', 'created_at', 'updated_at', 'created_by', 'updated_by',
        'is_deleted', 'deleted_at', 'deleted_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'sla_type', 'priority')
        }),
        ('SLA Configuration', {
            'fields': ('target_value', 'warning_threshold', 'conditions')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_escalation_enabled', 'escalation_recipients')
        }),
        ('Statistics', {
            'fields': ('total_incidents', 'met_sla_count', 'breached_sla_count', 'warning_count'),
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
        """Filter out soft-deleted SLAs"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_slas', 'deactivate_slas']
    
    def activate_slas(self, request, queryset):
        """Activate selected SLAs"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} SLAs activated.")
    activate_slas.short_description = "Activate selected SLAs"
    
    def deactivate_slas(self, request, queryset):
        """Deactivate selected SLAs"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} SLAs deactivated.")
    deactivate_slas.short_description = "Deactivate selected SLAs"


@admin.register(EmailTemplateVariable)
class EmailTemplateVariableAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'display_name', 'variable_type', 'is_required',
        'is_active', 'is_system', 'usage_count', 'last_used'
    ]
    list_filter = ['variable_type', 'is_required', 'is_active', 'is_system', 'created_at']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = [
        'id', 'usage_count', 'last_used', 'created_at', 'updated_at',
        'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'variable_type')
        }),
        ('Configuration', {
            'fields': ('default_value', 'is_required', 'validation_rules')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_system')
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
        """Filter out soft-deleted template variables"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_variables', 'deactivate_variables']
    
    def activate_variables(self, request, queryset):
        """Activate selected template variables"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} template variables activated.")
    activate_variables.short_description = "Activate selected variables"
    
    def deactivate_variables(self, request, queryset):
        """Deactivate selected template variables"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} template variables deactivated.")
    deactivate_variables.short_description = "Deactivate selected variables"


@admin.register(EmailIntegrationAnalytics)
class EmailIntegrationAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'period_type', 'webhook_events_received', 'automation_executions',
        'integration_syncs', 'webhook_success_rate', 'automation_success_rate'
    ]
    list_filter = ['period_type', 'date']
    search_fields = ['date']
    readonly_fields = [
        'id', 'webhook_success_rate', 'automation_success_rate',
        'integration_success_rate', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Time Period', {
            'fields': ('date', 'period_type')
        }),
        ('Webhook Metrics', {
            'fields': ('webhook_events_received', 'webhook_events_processed', 'webhook_events_failed', 'webhook_success_rate')
        }),
        ('Automation Metrics', {
            'fields': ('automation_executions', 'automation_successes', 'automation_failures', 'automation_success_rate')
        }),
        ('Integration Metrics', {
            'fields': ('integration_syncs', 'integration_successes', 'integration_failures', 'integration_success_rate')
        }),
        ('Response Times', {
            'fields': ('avg_webhook_processing_time', 'avg_automation_execution_time', 'avg_integration_sync_time'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).order_by('-date')
