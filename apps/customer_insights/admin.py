from django.contrib import admin
from django.utils.html import format_html
from .models import CustomerInsight
@admin.register(CustomerInsight)
class CustomerInsightAdmin(admin.ModelAdmin):
    """Admin for CustomerInsight model - simplified"""
    
    list_display = [
        'id', 'customer', 'is_cached', 'cache_status', 'calculated_at'
    ]
    list_filter = ['is_cached', 'calculated_at', 'created_at']
    search_fields = ['customer__customer_code', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['calculated_at', 'created_at', 'updated_at', 'cache_status']
    ordering = ['-calculated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('customer', 'is_cached', 'cache_expires_at', 'cache_status')
        }),
        ('Payment Insights', {
            'fields': ('payment_insights',),
            'classes': ('collapse',)
        }),
        ('Communication Insights', {
            'fields': ('communication_insights',),
            'classes': ('collapse',)
        }),
        ('Claims Insights', {
            'fields': ('claims_insights',),
            'classes': ('collapse',)
        }),
        ('Profile Insights', {
            'fields': ('profile_insights',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('calculated_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def cache_status(self, obj):
        """Display cache status with color coding"""
        if obj.is_cached and not obj.is_expired:
            return format_html('<span style="color: green;">✓ Cached (Valid)</span>')
        elif obj.is_cached and obj.is_expired:
            return format_html('<span style="color: orange;">⚠ Cached (Expired)</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Cached</span>')
    
    cache_status.short_description = 'Cache Status'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('customer')
