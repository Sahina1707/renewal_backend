from rest_framework import serializers
from .models import SmsProvider, SmsMessage


class SmsProviderSerializer(serializers.ModelSerializer):
    """
    Serializer for *displaying* SMS Providers. (Read-only)
    """
    provider_type_display = serializers.CharField(source='get_provider_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = SmsProvider
        fields = [
            'id', 'name', 'provider_type', 'provider_type_display', 'status', 'is_default',
            'is_active', 'rate_limit_per_minute', 'daily_limit', 'monthly_limit', 'messages_sent_total', 'last_sent_at',
            'created_at', 'created_by_name'
        ]


class SmsProviderCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for *creating and updating* SMS Providers.
    This bundles provider-specific fields into the 'credentials' JSON field.
    """
    # --- TWILIO FIELDS ---
    twilio_account_sid = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_auth_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_from_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    twilio_messaging_service_sid = serializers.CharField(write_only=True, required=False, allow_blank=True)

    # --- MSG91 FIELDS ---
    msg91_auth_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    msg91_sender_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    msg91_route = serializers.CharField(write_only=True, required=False, allow_blank=True)
    msg91_country_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    # --- AWS SNS FIELDS ---
    aws_sns_access_key_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    aws_sns_secret_access_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    aws_sns_region = serializers.CharField(write_only=True, required=False, allow_blank=True)

    # --- TEXTLOCAL FIELDS ---
    textlocal_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    textlocal_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    textlocal_hash = serializers.CharField(write_only=True, required=False, allow_blank=True)
    textlocal_sender = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = SmsProvider
        fields = [
            'id', 'name', 'provider_type', 'is_active', 'is_default',
            'rate_limit_per_minute', 'daily_limit', 'monthly_limit',
            # Twilio
            'twilio_account_sid', 'twilio_auth_token', 'twilio_from_number', 'twilio_messaging_service_sid',
            # MSG91
            'msg91_auth_key', 'msg91_sender_id', 'msg91_route', 'msg91_country_code',
            # AWS
            'aws_sns_access_key_id', 'aws_sns_secret_access_key', 'aws_sns_region',
            # TextLocal
            'textlocal_api_key',
            'textlocal_username', 'textlocal_hash', 'textlocal_sender',
        ]

    def _bundle_credentials(self, validated_data):
        """Gathers provider-specific fields into a credentials dictionary."""
        credentials = {}
        provider_type = validated_data.get('provider_type', getattr(self.instance, 'provider_type', None))
        
        CREDENTIAL_KEYS = {
            'twilio': ['twilio_account_sid', 'twilio_auth_token', 'twilio_from_number', 'twilio_messaging_service_sid'],
            'msg91': ['msg91_auth_key', 'msg91_sender_id', 'msg91_route', 'msg91_country_code'],
            'aws_sns': ['aws_sns_access_key_id', 'aws_sns_secret_access_key', 'aws_sns_region'],
            'textlocal': ['textlocal_api_key', 'textlocal_username', 'textlocal_hash', 'textlocal_sender'],
        }

        for key in CREDENTIAL_KEYS.get(provider_type, []):
            if key in validated_data:
                credentials[key] = validated_data.pop(key)
        return credentials

    def create(self, validated_data):
        credentials = self._bundle_credentials(validated_data)
        validated_data['credentials'] = credentials
        return super().create(validated_data)

    def update(self, instance, validated_data):
        new_credentials = self._bundle_credentials(validated_data)
        
        # Merge new credentials with existing ones (so we don't overwrite with blanks if partial update)
        if new_credentials:
            updated_credentials = instance.credentials.copy()
            updated_credentials.update(new_credentials)
            instance.credentials = updated_credentials
        
        return super().update(instance, validated_data)


class SmsMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying SMS message logs.
    """
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    class Meta:
        model = SmsMessage
        fields = [
            'id', 'provider_name', 'to_phone_number', 'from_number', 'content',
            'status', 'error_message', 'sent_at', 'created_at'
        ]