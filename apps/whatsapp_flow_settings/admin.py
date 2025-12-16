from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from .models import WhatsAppConfiguration, WhatsAppAccessPermission

@admin.register(WhatsAppConfiguration)
class WhatsAppConfigurationAdmin(admin.ModelAdmin):
    """
    Custom Admin to make the model behave like a 'Settings Page'.
    """
    # Group fields to match the sections in your Video
    fieldsets = (
        ("API Credentials", {
            "fields": ("phone_number_id", "access_token", "webhook_url", "verify_token", "is_enabled"),
            "description": "Get these details from the Meta for Developers Dashboard."
        }),
        ("Business Hours & Timezone", {
            "fields": ("enable_business_hours", "business_start_time", "business_end_time", "timezone"),
        }),
        ("Rate Limiting & Safety", {
            "fields": ("enable_rate_limiting", "messages_per_minute", "messages_per_hour", "fallback_message"),
        }),
    )

    def has_add_permission(self, request):
        # Disable "Add" button if a config object already exists
        if WhatsAppConfiguration.objects.exists():
            return False
        return super().has_add_permission(request)

    def changelist_view(self, request, extra_context=None):
        # If a config exists, redirect straight to the 'Edit' page. 
        # Skip the list view entirely.
        config = WhatsAppConfiguration.objects.first()
        if config:
            return redirect(reverse('admin:whatsapp_flow_settings_whatsappconfiguration_change', args=[config.id]))
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(WhatsAppAccessPermission)
class WhatsAppAccessPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
    # autocomplete_fields = ['user']  # Requires a search_field on User model