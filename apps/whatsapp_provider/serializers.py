import uuid
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.conf import settings
from cryptography.fernet import Fernet
from .models import (
    WhatsAppProvider, # Renamed
    WhatsAppPhoneNumber,
    WhatsAppMessageTemplate,
    WhatsAppMessage,
    WhatsAppWebhookEvent,
    WhatsAppFlow,
    WhatsAppAccountHealthLog,
    WhatsAppAccountUsageLog,
)
from apps.whatsapp_provider.services import WhatsAppService, WhatsAppAPIError
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# --- Helper function for encryption ---
def _encrypt_value(value):
    encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
    if not encryption_key or not value:
        logger.warning("Encrypt: No key or value, returning raw value.")
        return value
    try:
        fernet = Fernet(encryption_key.encode())
        return fernet.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return value

# --- Helper function for decryption ---
def _decrypt_value(value):
    encryption_key = getattr(settings, 'WHATSAPP_ENCRYPTION_KEY', None)
    if not encryption_key or not value:
        logger.warning("Decrypt: No key or value, returning raw value.")
        return value
    try:
        fernet = Fernet(encryption_key.encode())
        return fernet.decrypt(value.encode()).decode()
    except Exception as e:
        logger.warning(f"Decryption failed, returning raw value: {e}")
        return value # Return raw value if decryption fails (e.g., already plain text)


class WhatsAppPhoneNumberSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp phone numbers"""
    class Meta:
        model = WhatsAppPhoneNumber
        fields = [
            'id', 'provider', 'phone_number_id', 'phone_number', 'display_phone_number',
            'status', 'is_primary', 'is_active', 'quality_rating',
            'messages_sent_today', 'messages_sent_this_month',
            'last_message_sent', 'created_at', 'updated_at', 'verified_at'
        ]
        read_only_fields = [
            'id', 'messages_sent_today', 'messages_sent_this_month',
            'last_message_sent', 'created_at', 'updated_at', 'verified_at'
        ]


class WhatsAppMessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp message templates"""
    class Meta:
        model = WhatsAppMessageTemplate
        fields = [
            'id', 'provider', 'name', 'category', 'language', 'header_text', 'body_text',
            'footer_text', 'components', 'status', 'meta_template_id',
            'rejection_reason', 'usage_count', 'last_used',
            'created_at', 'updated_at', 'approved_at'
        ]
        read_only_fields = [
            'id', 'meta_template_id', 'rejection_reason', 'usage_count',
            'last_used', 'created_at', 'updated_at', 'approved_at'
        ]


class WhatsAppProviderSerializer(serializers.ModelSerializer):
    """
    Serializer for *displaying* WhatsApp Providers.
    (READ-ONLY)
    """
    phone_numbers = WhatsAppPhoneNumberSerializer(many=True, read_only=True)
    message_templates = WhatsAppMessageTemplateSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    provider_type_display = serializers.CharField(source='get_provider_type_display', read_only=True)
    
    # We dynamically add decrypted credentials for display
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add decrypted (or raw) credentials for display, excluding sensitive keys
        credentials = {}
        sensitive_keys = ['meta_access_token', 'twilio_auth_token', 'gupshup_api_key', 'dialog_api_key']
        
        for key, value in instance.credentials.items():
            if key not in sensitive_keys:
                credentials[key] = _decrypt_value(value)
            else:
                credentials[key] = "********" 
        
        data['credentials'] = credentials
        return data

    class Meta:
        model = WhatsAppProvider
        fields = [
            'id', 'name', 'provider_type', 'provider_type_display',
            'business_name', 'business_description', 'business_email',
            'status', 'quality_rating', 'health_status', 'last_health_check',
            'daily_limit', 'monthly_limit', 'rate_limit_per_minute',
            'messages_sent_today', 'messages_sent_this_month',
            'is_default', 'is_active',
            'phone_numbers', 'message_templates', 'created_by_name',
            'updated_by_name', 'created_at', 'updated_at',
            # Bot config
            'enable_auto_reply', 'use_knowledge_base', 'greeting_message',
            'fallback_message', 'enable_business_hours',
            'business_hours_start', 'business_hours_end', 'business_timezone',
        ]
        # Excludes 'credentials' field by default, added manually in to_representation


class WhatsAppProviderCreateUpdateSerializer(serializers.ModelSerializer): # Renamed
    """
    Serializer for *creating and updating* WhatsApp Providers.
    This serializer accepts provider-specific fields and bundles them into the 'credentials' JSON field.
    """
    meta_access_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    meta_phone_number_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    meta_business_account_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_account_sid = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_auth_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_from_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    meta_api_version = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_status_callback_url = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Add other provider fields as needed

    class Meta:
        model = WhatsAppProvider
        fields = [
            'id', 'name', 'provider_type', 'is_active', 'is_default',
            'webhook_verify_token',
            # Add the provider-specific fields to the list
            'meta_access_token', 'meta_phone_number_id', 'meta_business_account_id',
            'meta_api_version', 'twilio_account_sid', 'twilio_auth_token', 
            'twilio_from_number', 'twilio_status_callback_url',
        ]
        read_only_fields = ['id', 'webhook_verify_token']

    def _bundle_and_encrypt_credentials(self, validated_data):
        """
        Gathers provider-specific fields from validated_data,
        encrypts them, and returns them as a credentials dictionary.
        """
        credentials = {}
        # Use provider_type from instance if updating, otherwise from validated_data
        provider_type = validated_data.get('provider_type') or (self.instance and self.instance.provider_type)

        # Define which keys belong to which provider
        PROVIDER_CREDENTIAL_KEYS = {
            'meta': [
            'meta_access_token', 
            'meta_phone_number_id', 
            'meta_business_account_id', 
            'meta_api_version'
        ],
            'twilio': [
            'twilio_account_sid', 
            'twilio_auth_token', 
            'twilio_from_number', 
            'twilio_status_callback_url' 
        ],
            # Add other providers and their keys here
        }

        credential_keys = PROVIDER_CREDENTIAL_KEYS.get(provider_type, [])

        for key in credential_keys:
            if key in validated_data:
                value = validated_data.pop(key) 
                if value:
                    # Encrypt sensitive tokens
                    if 'token' in key or 'key' in key:
                         credentials[key] = _encrypt_value(value)
                    else:
                         credentials[key] = value
        
        return credentials

    def create(self, validated_data):
        """
        Create a new WhatsApp Provider instance.
        """
        credentials = self._bundle_and_encrypt_credentials(validated_data)
        validated_data['credentials'] = credentials

        # Generate a webhook verify token if one isn't provided
        if not validated_data.get('webhook_verify_token'):
            validated_data['webhook_verify_token'] = str(uuid.uuid4())

        # Handle 'is_default' logic
        if validated_data.get('is_default', False):
            WhatsAppProvider.objects.filter(is_default=True).update(is_default=False)

        provider = WhatsAppProvider.objects.create(**validated_data)
        return provider
    
    def update(self, instance, validated_data):
        """
        Update an existing WhatsApp Provider instance.
        """
        # Handle 'is_default' logic
        if validated_data.get('is_default', False) and not instance.is_default:
            WhatsAppProvider.objects.filter(is_default=True).exclude(pk=instance.pk).update(is_default=False)

        # Get new credentials and merge them with existing ones
        new_credentials = self._bundle_and_encrypt_credentials(validated_data)
        
        # Start with the existing credentials and update them
        # This ensures we don't lose credentials for other providers if not all are sent
        updated_credentials = instance.credentials.copy()
        updated_credentials.update(new_credentials)
        
        instance.credentials = updated_credentials

        # Update other fields on the instance
        instance.name = validated_data.get('name', instance.name)
        instance.provider_type = validated_data.get('provider_type', instance.provider_type)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.is_default = validated_data.get('is_default', instance.is_default)
        
        instance.save()
        return instance

class MessageSendSerializer(serializers.Serializer):
    """
    New, simpler serializer for the 'send_message' ViewSet action.
    The provider is determined by the URL.
    """
    to_phone_number = serializers.CharField(max_length=20, required=True)
    message_type = serializers.ChoiceField(choices=[
        ('text', 'Text Message'),
        ('template', 'Template Message'),
        ('interactive', 'Interactive Message'),
    ], default='text')
    
    # For text messages
    text_content = serializers.CharField(required=False, allow_blank=True)
    
    # For template messages
    template_id = serializers.IntegerField(required=False)
    template_params = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    
    # For interactive messages
    flow_id = serializers.IntegerField(required=False)
    flow_token = serializers.CharField(required=False, allow_blank=True)
    
    # Additional options
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    campaign_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_to_phone_number(self, value):
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must include country code (e.g., +1234567890)")
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

# --- Message Serializers (from original file, updated) ---

class WhatsAppMessageSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp messages"""
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

# --- Other Serializers (from original file, updated) ---

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
class TemplateProviderLinkSerializer(serializers.Serializer):
    """
    Serializer to validate the provider_id for linking.
    """
    provider_id = serializers.IntegerField(required=True)

    def validate_provider_id(self, value):
        """
        Check that the provider exists.
        """
        try:
            # Note: We are validating against the main WhatsAppProvider model
            provider = WhatsAppProvider.objects.get(id=value, is_deleted=False)
        except WhatsAppProvider.DoesNotExist:
            raise serializers.ValidationError("A provider with this ID does not exist.")
        return value