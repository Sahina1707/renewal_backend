from django.contrib import admin
from .models import DistributionChannel


@admin.register(DistributionChannel)
class DistributionChannelAdmin(admin.ModelAdmin):
    """Admin configuration for DistributionChannel model"""
    
    list_display = [
        'name',
        'channel_type',
        'status',
        'contact_person',
        'region',
        'commission_rate',
        'partner_since',
        'created_at',
    ]
    list_filter = [
        'channel_type',
        'status',
        'region',
        'partner_since',
        'created_at',
    ]
    search_fields = [
        'name',
        'description',
        'contact_person',
        'contact_email',
        'contact_phone',
        'region',
    ]
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'channel_type', 'description', 'channel')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_email', 'contact_phone', 'region')
        }),
        ('Financial Information', {
            'fields': ('commission_rate', 'target_revenue')
        }),
        ('Status & Metadata', {
            'fields': ('status', 'partner_since')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Set created_by/updated_by when saving"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
