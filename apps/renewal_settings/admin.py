from django.contrib import admin
from .models import RenewalSettings

@admin.register(RenewalSettings)
class RenewalSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'auto_refresh_enabled', 
        'enable_call_integration', 
        'active_provider',
        'default_call_duration'
    ]
    
    # Organize fields nicely in admin
    fieldsets = (
        ('General Settings', {
            'fields': ('auto_refresh_enabled', 'show_edit_case_button')
        }),
        ('Call Integration', {
            'fields': (
                'enable_call_integration', 
                'active_provider', 
                'enforce_provider_limits'
            )
        }),
        ('Call Configuration', {
            'fields': (
                'default_call_duration', 
                'max_concurrent_calls', 
                'enable_call_recording', 
                'enable_call_analytics'
            )
        }),
    )

    def has_add_permission(self, request):
        # Prevent creating multiple setting rows
        return not RenewalSettings.objects.exists()