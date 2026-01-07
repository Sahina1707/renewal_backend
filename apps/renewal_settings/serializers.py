from rest_framework import serializers
from .models import RenewalSettings
from apps.call_provider.models import CallProviderConfig
from apps.call_provider.serializers import CallProviderConfigSerializer

# =========================================================
#  GLOBAL CAPABILITIES (The Rulebook)
# =========================================================
# Defines what each provider is physically capable of.
PROVIDER_CAPABILITIES = {
    'twilio': {'recording': True, 'analytics': True, 'max_limit': 100, 'max_duration': 240},
    'exotel': {'recording': True, 'analytics': True, 'max_limit': 50,  'max_duration': 60},
    'ubona':  {'recording': False, 'analytics': False, 'max_limit': 20, 'max_duration': 30},
    'custom': {'recording': True, 'analytics': True, 'max_limit': 100, 'max_duration': 120}
}

class RenewalSettingsSerializer(serializers.ModelSerializer):
    # Nested serializer to show nice details (Name, Type) in the JSON response
    active_provider_details = CallProviderConfigSerializer(source='active_provider', read_only=True)
    
    # =========================================================
    #  CREDENTIAL INPUTS (Write Only - Pass Through)
    # =========================================================
    # These fields do NOT exist in RenewalSettings. We define them here so the 
    # Frontend can send them, and our View will extract and save them to the Provider table.
    
    # 1. Twilio Credentials
    twilio_account_sid = serializers.CharField(required=False, allow_blank=True, write_only=True)
    twilio_auth_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    twilio_from_number = serializers.CharField(required=False, allow_blank=True, write_only=True)
    
    # 2. Exotel Credentials
    exotel_api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    exotel_api_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    exotel_subdomain = serializers.CharField(required=False, allow_blank=True, write_only=True)
    exotel_account_sid = serializers.CharField(required=False, allow_blank=True, write_only=True)
    exotel_caller_id = serializers.CharField(required=False, allow_blank=True, write_only=True)

    # 3. Ubona Credentials
    ubona_api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    ubona_api_url = serializers.CharField(required=False, allow_blank=True, write_only=True)
    ubona_account_sid = serializers.CharField(required=False, allow_blank=True, write_only=True)
    ubona_caller_id = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = RenewalSettings
        fields = [
            'id',
            # Global Settings
            'auto_refresh_enabled',
            'show_edit_case_button',
            'enforce_provider_limits',
            
            # Policy Processing (Slider & Auto-Assign)
            'default_renewal_period',
            'auto_assign_cases',
            
            # The Active Switch
            'enable_call_integration',
            
            # Integration Status
            'is_call_integration_testing',
            'is_sms_integration_testing',
            'is_whatsapp_integration_testing',
            
            # Specific Settings
            'default_call_duration',
            'max_concurrent_calls',
            'enable_call_recording',
            'enable_call_analytics',
            
            # Provider Links
            'active_provider', 
            'active_provider_details',
            
            # Credential Fields (Write Only)
            'twilio_account_sid', 'twilio_auth_token', 'twilio_from_number',
            'exotel_api_key', 'exotel_api_token', 'exotel_subdomain', 'exotel_account_sid', 'exotel_caller_id',
            'ubona_api_key', 'ubona_api_url', 'ubona_account_sid', 'ubona_caller_id',
        ]
        read_only_fields = [
            'active_provider', 
            'id', 
            'is_call_integration_testing', 
            'is_sms_integration_testing', 
            'is_whatsapp_integration_testing'
        ]

    def validate(self, data):
        """
        Validation Logic: 
        Ensures the user doesn't try to set a Limit or Feature that the Provider doesn't support.
        """
        
        # 1. Identify which provider we are validating against.
        # If we are updating an existing row, use that row's provider.
        current_type = None
        if self.instance and self.instance.active_provider:
            current_type = self.instance.active_provider.provider_type
        
        # If we can't find the provider type (rare case), skip validation
        if not current_type:
            return data

        # 2. Get the rules for this provider (e.g., Exotel rules)
        rules = PROVIDER_CAPABILITIES.get(current_type, {})
        
        # 3. Check Recording Support
        if data.get('enable_call_recording') and not rules.get('recording'):
             raise serializers.ValidationError({
                 "enable_call_recording": f"{current_type.capitalize()} does not support Call Recording."
             })

        # 4. Check Analytics Support
        if data.get('enable_call_analytics') and not rules.get('analytics'):
             raise serializers.ValidationError({
                 "enable_call_analytics": f"{current_type.capitalize()} does not support Call Analytics."
             })
             
        # 5. Check Duration Limit
        req_duration = data.get('default_call_duration')
        allow_duration = rules.get('max_duration', 0)
        
        # Only check if Enforce Limit is True (default behavior) or if not passed
        if req_duration and allow_duration > 0 and req_duration > allow_duration:
            raise serializers.ValidationError({
                "default_call_duration": f"{current_type.capitalize()} allows max duration of {allow_duration} minutes."
            })

        # 6. Check Concurrent Call Limit
        req_limit = data.get('max_concurrent_calls')
        allow_limit = rules.get('max_limit', 0)
        
        if req_limit and allow_limit > 0 and req_limit > allow_limit:
            raise serializers.ValidationError({
                "max_concurrent_calls": f"{current_type.capitalize()} allows max {allow_limit} concurrent calls."
            })

        return data


class QuickMessageSettingsSerializer(serializers.ModelSerializer):
    # Nested serializer for viewing details
    from apps.sms_provider.models import SmsProvider
    from apps.whatsapp_provider.models import WhatsAppProvider

    # =========================================================
    #  CREDENTIAL INPUTS (Write Only - Pass Through)
    # =========================================================
    
    # --- WhatsApp Credentials ---
    wa_access_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    wa_phone_number_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    wa_business_account_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    
    # --- SMS Credentials ---
    # Common fields, mapped dynamically in View
    sms_api_key = serializers.CharField(required=False, allow_blank=True, write_only=True) 
    sms_auth_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    sms_sender_id = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        from .models import QuickMessageSettings
        model = QuickMessageSettings
        fields = [
            'id',
            'enable_quick_message_integration',
            'active_sms_provider',
            'active_whatsapp_provider',
            
            # Analytics & Limits
            'enable_delivery_reports',
            'enable_message_analytics',
            'rate_limit_per_minute',
            'daily_message_limit',
            
            # Templates
            'policy_renewal_reminder_template',
            'claim_status_update_template',
            'payment_confirmation_template',
            
            # Credential Passthrough
            'wa_access_token', 'wa_phone_number_id', 'wa_business_account_id',
            'sms_api_key', 'sms_auth_token', 'sms_sender_id'
        ]