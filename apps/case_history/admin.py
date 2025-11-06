from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import CaseHistory
from apps.renewals.models import RenewalCase as Case

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    """Admin interface for Case model."""
    
    list_display = [
        'case_number', 'get_title', 'status', 'assigned_to', 
        'customer', 'get_processing_days', 'created_at'
    ]
    list_filter = [
        'status', 'assigned_to', 'customer', 
        'created_at', 'payment_status'
    ]
    search_fields = [
        'case_number', 'notes', 'assigned_to__email',
        'customer__first_name', 'customer__last_name', 'customer__email'
    ]
    readonly_fields = ['case_number', 'get_processing_days', 'created_at', 'updated_at']
    raw_id_fields = ['assigned_to', 'customer', 'policy']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('case_number', 'notes', 'status')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'customer', 'policy')
        }),
        ('Financial', {
            'fields': ('renewal_amount', 'payment_status', 'batch_code')
        }),
        ('Timing', {
            'fields': ('created_at', 'updated_at', 'get_processing_days')
        }),
        ('Audit Information', {
            'fields': ('created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_title(self, obj):
        """Get case title from customer and policy info"""
        if obj.customer and obj.policy:
            return f"Renewal for {obj.customer.full_name} - {obj.policy.policy_number}"
        elif obj.customer:
            return f"Renewal for {obj.customer.full_name}"
        else:
            return f"Renewal Case {obj.case_number}"
    get_title.short_description = 'Title'
    
    def get_processing_days(self, obj):
        """Calculate processing days"""
        if obj.created_at:
            from django.utils import timezone
            delta = timezone.now() - obj.created_at
            return delta.days
        return 0
    get_processing_days.short_description = 'Processing Days'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'assigned_to', 'customer', 'policy', 'created_by', 'updated_by'
        )


@admin.register(CaseHistory)
class CaseHistoryAdmin(admin.ModelAdmin):
    """Admin interface for CaseHistory model."""
    
    list_display = [
        'case', 'action', 'description_short', 'created_by', 'created_at'
    ]
    list_filter = [
        'action', 'created_by', 'created_at', 'case__status'
    ]
    search_fields = [
        'case__case_id', 'description', 'action', 'created_by__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['case', 'created_by']
    
    fieldsets = (
        ('History Information', {
            'fields': ('case', 'action', 'description')
        }),
        ('Change Details', {
            'fields': ('old_value', 'new_value'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def description_short(self, obj):
        """Display truncated description."""
        if len(obj.description) > 50:
            return f"{obj.description[:50]}..."
        return obj.description
    description_short.short_description = 'Description'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'case', 'created_by', 'updated_by'
        )
