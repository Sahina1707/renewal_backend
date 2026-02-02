from rest_framework import serializers
from .models import CampaignSetting
from apps.email_provider.models import EmailProviderConfig
from apps.sms_provider.models import SmsProvider
from apps.whatsapp_provider.models import WhatsAppProvider
class EmailOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailProviderConfig
        fields = ['id', 'name', 'from_email', 'provider_type']
class SMSOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsProvider
        fields = ['id', 'name', 'provider_type']
class WhatsAppOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppProvider
        fields = ['id', 'name', 'business_name', 'provider_type']
class CampaignSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSetting
        fields = [
            'id',
            'email_provider', 'sms_provider', 'whatsapp_provider',
            'consent_required', 'dnd_compliance', 'opt_in_required', 'data_retention_days',
            'email_rate_limit', 'sms_rate_limit', 'whatsapp_rate_limit',
            'batch_size', 'retry_attempts',
            'template_approval_required', 'dlt_template_required', 'auto_save_templates',
            'tracking_enabled', 'webhook_url', 'reporting_interval', 'export_format'
            ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        if instance.email_provider:
            rep['email_provider'] = EmailOptionSerializer(instance.email_provider).data
        if instance.sms_provider:
            rep['sms_provider'] = SMSOptionSerializer(instance.sms_provider).data
        if instance.whatsapp_provider:
            rep['whatsapp_provider'] = WhatsAppOptionSerializer(instance.whatsapp_provider).data
            
        return rep