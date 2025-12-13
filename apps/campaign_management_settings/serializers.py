from rest_framework import serializers
from .models import CampaignSetting

# --- IMPORT EXTERNAL MODELS ---
from apps.email_provider.models import EmailProviderConfig
from apps.sms_provider.models import SmsProvider
from apps.whatsapp_provider.models import WhatsAppProvider

# --- HELPER SERIALIZERS (Fixed Field Names) ---

class EmailOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailProviderConfig
        # ✅ FIX: Use 'name', not 'config_name'
        fields = ['id', 'name', 'from_email', 'provider_type']

class SMSOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsProvider
        # ✅ FIX: Use 'name', not 'provider_name'
        fields = ['id', 'name', 'provider_type']

class WhatsAppOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppProvider
        # ✅ FIX: Ensure 'name' matches your WhatsApp model
        fields = ['id', 'name', 'business_name', 'provider_type']

class CampaignSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSetting
        fields = [
            'id',
            # Providers
            'email_provider', 'sms_provider', 'whatsapp_provider',
            
            # Compliance
            'consent_required', 'dnd_compliance', 'opt_in_required', 'data_retention_days',
            
            # Rate Limiting
            'email_rate_limit', 'sms_rate_limit', 'whatsapp_rate_limit',
            'batch_size', 'retry_attempts',
            
            # Template
            'template_approval_required', 'dlt_template_required', 'auto_save_templates',
            
            # Analytics
            'tracking_enabled', 'webhook_url', 'reporting_interval', 'export_format'
            ]

    def to_representation(self, instance):
        """
        Swaps IDs with full object details for the frontend dropdowns.
        """
        rep = super().to_representation(instance)
        
        if instance.email_provider:
            rep['email_provider'] = EmailOptionSerializer(instance.email_provider).data
        if instance.sms_provider:
            rep['sms_provider'] = SMSOptionSerializer(instance.sms_provider).data
        if instance.whatsapp_provider:
            rep['whatsapp_provider'] = WhatsAppOptionSerializer(instance.whatsapp_provider).data
            
        return rep