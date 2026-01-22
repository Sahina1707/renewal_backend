from django.db import models
from apps.call_provider.models import CallProviderConfig

class RenewalSettings(models.Model):
    # =========================================================
    #  RELATIONSHIP (Row Per Provider Strategy)
    # =========================================================
    # This ensures every Provider (Twilio, Exotel) gets its own Profile Row.
    active_provider = models.OneToOneField(
        CallProviderConfig, 
        on_delete=models.CASCADE, 
        related_name="renewal_setting_profile"
    )

    # =========================================================
    #  THE "ACTIVE" SWITCH
    # =========================================================
    # Only ONE row in this entire table should have this set to True at a time.
    enable_call_integration = models.BooleanField(default=False)
    
    # =========================================================
    #  INTEGRATION TESTING STATUS (Persisted)
    # =========================================================
    # Updates across ALL rows when a test is run.
    is_call_integration_testing = models.BooleanField(default=False, help_text="Status of Call Integration Test")
    is_sms_integration_testing = models.BooleanField(default=False, help_text="Status of SMS Integration Test")
    is_whatsapp_integration_testing = models.BooleanField(default=False, help_text="Status of WhatsApp Integration Test")

    # =========================================================
    #  GLOBAL SETTINGS (Synced Across All Rows)
    # =========================================================
    # These settings technically exist in every row, but our View ensures 
    # they stay identical (synced) for a consistent user experience.
    auto_refresh_enabled = models.BooleanField(default=True)
    show_edit_case_button = models.BooleanField(default=True)
    enforce_provider_limits = models.BooleanField(default=True)
    
    # Policy Processing Settings
    default_renewal_period = models.PositiveIntegerField(
        default=30,
        help_text="Days before expiry to start renewal process (Slider Value)"
    )
    auto_assign_cases = models.BooleanField(
        default=False,
        help_text="Automatically assign new cases to available agents"
    )

    # =========================================================
    #  SPECIFIC SETTINGS (Unique Per Provider)
    # =========================================================
    # These settings are unique to the active provider (e.g., Twilio=60min, Exotel=30min).
    default_call_duration = models.PositiveIntegerField(
        default=30, 
        help_text="Default call duration in minutes"
    )
    max_concurrent_calls = models.PositiveIntegerField(
        default=10,
        help_text="Maximum concurrent calls allowed"
    )
    enable_call_recording = models.BooleanField(default=True)
    enable_call_analytics = models.BooleanField(default=False)

    class Meta:
        db_table = "renewal_settings"
        verbose_name = "Renewal Setting"
        verbose_name_plural = "Renewal Settings"

    def __str__(self):
        return f"Settings Profile for {self.active_provider.name}"


class QuickMessageSettings(models.Model):
    # =========================================================
    #  RELATIONSHIPS
    # =========================================================
    # Links to the currently selected active providers for SMS and WhatsApp
    active_sms_provider = models.ForeignKey(
        'sms_provider.SmsProvider', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="quick_message_settings_active"
    )
    active_whatsapp_provider = models.ForeignKey(
        'whatsapp_provider.WhatsAppProvider', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="quick_message_settings_active"
    )

    # =========================================================
    #  MAIN TOGGLE & HISTORY
    # =========================================================
    enable_quick_message_integration = models.BooleanField(default=False)
    is_active_configuration = models.BooleanField(default=True, help_text="Only one row should be active at a time.")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # =========================================================
    #  ANALYTICS & DELIVERABILITY
    # =========================================================
    enable_delivery_reports = models.BooleanField(default=True)
    enable_message_analytics = models.BooleanField(default=False)

    # =========================================================
    #  LIMITS (Specific to this Integration)
    # =========================================================
    rate_limit_per_minute = models.PositiveIntegerField(
        default=60,
        help_text="Rate limit (messages/minute)"
    )
    daily_message_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Daily message limit"
    )

    # =========================================================
    #  DEFAULT TEMPLATES
    # =========================================================
    policy_renewal_reminder_template = models.TextField(
        default="Hi {{customerName}}, your {{policyType}} policy {{policyNumber}} is due for renewal on {{renewalDate}}. Please contact us to renew.",
        help_text="Template for Policy Renewal Reminder"
    )
    claim_status_update_template = models.TextField(
        default="Hello {{customerName}}, your claim {{claimNumber}} status has been updated to {{status}}. For queries, call us.",
        help_text="Template for Claim Status Update"
    )
    payment_confirmation_template = models.TextField(
        default="Thank you {{customerName}}! We have received your payment of {{amount}} for policy {{policyNumber}}. Receipt: {{receiptNumber}}",
        help_text="Template for Payment Confirmation"
    )

    class Meta:
        db_table = "quick_message_settings"
        verbose_name = "Quick Message Setting"
        verbose_name_plural = "Quick Message Settings"

    def __str__(self):
        return "Quick Message Integration Settings"