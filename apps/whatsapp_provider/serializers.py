import uuid
import logging
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.conf import settings
from cryptography.fernet import Fernet
from .models import (
    WhatsAppProvider, WhatsAppPhoneNumber, WhatsAppMessageTemplate,
    WhatsAppMessage, WhatsAppWebhookEvent, WhatsAppFlow,
    WhatsAppAccountHealthLog, WhatsAppAccountUsageLog
)

logger = logging.getLogger(__name__)
User = get_user_model()

def _encrypt_value(value):
    encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
    if not encryption_key or not value:
        return value
    try:
        fernet = Fernet(encryption_key.encode())
        return fernet.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return value

def _decrypt_value(value):
    encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
    if not encryption_key or not value:
        return value
    try:
        fernet = Fernet(encryption_key.encode())
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value
class WhatsAppProviderSerializer(serializers.ModelSerializer):
    phone_numbers = serializers.StringRelatedField(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = WhatsAppProvider
        fields = [
            'id', 'name', 'provider_type', 'business_name',
            'status', 'quality_rating', 'health_status',
            'account_id', 'phone_number_id', 'app_id', 'api_version', 'api_url',
            'is_default', 'is_active', 'created_by_name', 'created_at',
            'enable_auto_reply', 'greeting_message', 'phone_numbers'
        ]

class WhatsAppProviderCreateUpdateSerializer(serializers.ModelSerializer):
    credentials = serializers.JSONField(required=False)

    class Meta:
        model = WhatsAppProvider
        fields = '__all__'
        read_only_fields = ['id', 'webhook_verify_token', 'created_by', 'updated_by']
        extra_kwargs = {
            'credentials': {'required': False},
        }

    def validate(self, data):
        if 'credentials' in data:
            for key in ['auth_token', 'access_token']:
                if key in data['credentials']:
                    data['credentials'][key] = _encrypt_value(data['credentials'][key])

        if not data.get('webhook_verify_token') and not self.instance:
            data['webhook_verify_token'] = str(uuid.uuid4())

        return data

    def create(self, validated_data):
        if validated_data.get('is_default', False):
            WhatsAppProvider.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get('is_default', False) and not instance.is_default:
            WhatsAppProvider.objects.filter(is_default=True).exclude(pk=instance.pk).update(is_default=False)
        return super().update(instance, validated_data)

class WhatsAppPhoneNumberSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    class Meta:
        model = WhatsAppPhoneNumber
        fields = [
            'id', 'provider', 'provider_name', 'phone_number_id', 
            'phone_number', 'display_phone_number', 'status', 
            'is_primary', 'is_active', 'quality_rating', 
            'messages_sent_today', 'created_at', 'verified_at'
        ]
        read_only_fields = [
            'messages_sent_today', 'messages_sent_this_month', 
            'created_at', 'updated_at', 'verified_at'
        ]

class WhatsAppMessageTemplateSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = WhatsAppMessageTemplate
        fields = [
            'id', 'provider', 'provider_name', 'name', 'category', 'language',
            'header_text', 'body_text', 'footer_text', 'components',
            'status', 'meta_template_id', 'rejection_reason',
            'usage_count', 'last_used', 'created_by_name', 'created_at', 'approved_at'
        ]
        read_only_fields = [
            'status', 'meta_template_id', 'usage_count', 
            'last_used', 'created_at', 'approved_at'
        ]

class TemplateProviderLinkSerializer(serializers.Serializer):
   
    provider_id = serializers.IntegerField(required=True)

    def validate_provider_id(self, value):
        try:
            WhatsAppProvider.objects.get(id=value, is_deleted=False)
        except WhatsAppProvider.DoesNotExist:
            raise serializers.ValidationError("A provider with this ID does not exist.")
        return value

class MessageSendSerializer(serializers.Serializer):
    to_phone_number = serializers.CharField(max_length=20, required=True)
    message_type = serializers.ChoiceField(choices=[
        ('text', 'Text Message'),
        ('template', 'Template Message'),
        ('interactive', 'Interactive Message'),
    ], default='text')
    
    text_content = serializers.CharField(required=False, allow_blank=True)
    
    template_id = serializers.IntegerField(required=False)
    template_params = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    
    flow_id = serializers.IntegerField(required=False)
    flow_token = serializers.CharField(required=False, allow_blank=True)
    
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    campaign_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_to_phone_number(self, value):
        value = value.replace(" ", "").replace("-", "")
        if not value.startswith('+'):
            pass 
        return value

    def validate(self, data):
        message_type = data.get('message_type')
        
        if message_type == 'text':
            if not data.get('text_content'):
                raise serializers.ValidationError({'text_content': 'This field is required for text messages.'})
        
        elif message_type == 'template':
            if not data.get('template_id'):
                raise serializers.ValidationError({'template_id': 'This field is required for template messages.'})
        
        elif message_type == 'interactive':
            if not data.get('flow_id'):
                raise serializers.ValidationError({'flow_id': 'This field is required for interactive messages.'})
        
        return data
class WhatsAppMessageSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    phone_number_display = serializers.CharField(source='phone_number.display_phone_number', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    customer_name = serializers.SerializerMethodField()
    
    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'message_id', 'direction', 'message_type', 'provider',
            'phone_number', 'template', 'to_phone_number', 'from_phone_number',
            'content', 'status', 'error_code', 'error_message', 'campaign',
            'customer', 'metadata', 'provider_name', 'phone_number_display',
            'template_name', 'customer_name', 'created_at', 'sent_at',
            'delivered_at', 'read_at'
        ]
        read_only_fields = [
            'id', 'message_id', 'created_at', 'sent_at', 'delivered_at', 'read_at'
        ]
    
    def get_customer_name(self, obj):
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}".strip()
        return None

class WhatsAppWebhookEventSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    class Meta:
        model = WhatsAppWebhookEvent
        fields = [
            'id', 'event_type', 'provider', 'message', 'raw_data',
            'processed', 'processing_error', 'provider_name',
            'received_at', 'processed_at'
        ]

class WhatsAppFlowSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    class Meta:
        model = WhatsAppFlow
        fields = [
            'id', 'provider', 'name', 'description', 'flow_json',
            'status', 'is_active', 'usage_count', 'last_used',
            'provider_name', 'created_by_name', 'created_at', 'updated_at'
        ]

class WhatsAppAccountHealthLogSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    class Meta:
        model = WhatsAppAccountHealthLog
        fields = [
            'id', 'provider', 'health_status', 'check_details',
            'error_message', 'provider_name', 'checked_at'
        ]

class WhatsAppAccountUsageLogSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    class Meta:
        model = WhatsAppAccountUsageLog
        fields = [
            'id', 'provider', 'date', 'messages_sent', 'messages_delivered',
            'messages_failed', 'messages_read', 'provider_name', 'created_at'
        ]