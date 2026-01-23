from rest_framework import serializers

from .models import (
    BotCallingProviderConfig,
    BotCallingProviderHealthLog,
    BotCallingProviderUsageLog,
    BotCallingProviderTestResult,
)
from .services import BotCallingProviderService
from .services import BotCallingProviderService

class BotCallingProviderConfigSerializer(serializers.ModelSerializer):
    provider_type_display = serializers.CharField(source='get_provider_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = BotCallingProviderConfig
        fields = [
            'id', 'name', 'provider_type', 'provider_type_display',
            'bot_script','ubona_api_key', 'ubona_api_url', 'ubona_account_sid', 'ubona_caller_id',
            'hoa_api_key', 'hoa_api_url', 'hoa_agent_id',
            'hoa_campaign_id', 'hoa_webhook_url',
            'gnani_api_key', 'gnani_api_url', 'gnani_bot_id',
            'gnani_project_id', 'gnani_language', 'gnani_voice_gender',
            'twilio_account_sid', 'twilio_auth_token', 'twilio_from_number',
            'twilio_status_callback_url', 'twilio_voice_url',
            'daily_limit', 'monthly_limit', 'rate_limit_per_minute',
            'priority', 'priority_display', 'is_default', 'is_active',
            'last_health_check', 'status', 'status_display',
            'calls_made_today', 'calls_made_this_month',
            'last_reset_daily', 'last_reset_monthly',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'is_deleted', 'deleted_at', 'deleted_by',
        ]

        read_only_fields = [
            'id',
            'created_at', 'updated_at',
            'created_by', 'updated_by',
            'last_health_check', 'status',
            'calls_made_today', 'calls_made_this_month',
            'last_reset_daily', 'last_reset_monthly',
            'is_deleted', 'deleted_at', 'deleted_by',
        ]

class BotCallingProviderConfigCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotCallingProviderConfig
        fields = [
            'name', 'provider_type',
            'bot_script',
            'ubona_api_key', 'ubona_api_url', 'ubona_account_sid', 'ubona_caller_id',
            'hoa_api_key', 'hoa_api_url', 'hoa_agent_id',
            'hoa_campaign_id', 'hoa_webhook_url',
            'gnani_api_key', 'gnani_api_url', 'gnani_bot_id',
            'gnani_project_id', 'gnani_language', 'gnani_voice_gender',
            'twilio_account_sid', 'twilio_auth_token', 'twilio_from_number',
            'twilio_status_callback_url', 'twilio_voice_url',
            'daily_limit', 'monthly_limit', 'rate_limit_per_minute',
            'priority', 'is_default', 'is_active',
        ]

    def create(self, validated_data):

        request = self.context.get('request')
        validated_data['created_by'] = request.user if request else None

        service = BotCallingProviderService()
        secret_fields = [
            'ubona_api_key',
            'hoa_api_key',
            'gnani_api_key',
            'twilio_auth_token',
        ]

        for field in secret_fields:
            if validated_data.get(field):
                validated_data[field] = service._encrypt_credential(validated_data[field])

        return super().create(validated_data)

class BotCallingProviderConfigUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotCallingProviderConfig
        fields = [
            'name',
            'bot_script',
            'ubona_api_key', 'ubona_api_url',
            'ubona_account_sid', 'ubona_caller_id',
            'hoa_api_key', 'hoa_api_url',
            'hoa_agent_id', 'hoa_campaign_id', 'hoa_webhook_url',
            'gnani_api_key', 'gnani_api_url',
            'gnani_bot_id', 'gnani_project_id',
            'gnani_language', 'gnani_voice_gender',
            'twilio_account_sid', 'twilio_auth_token',
            'twilio_from_number',
            'twilio_status_callback_url', 'twilio_voice_url',
            'daily_limit', 'monthly_limit',
            'rate_limit_per_minute',
            'priority', 'is_default', 'is_active',
        ]

    def update(self, instance, validated_data):

        request = self.context.get('request')
        service = BotCallingProviderService()

        secret_fields = [
            'ubona_api_key',
            'hoa_api_key',
            'gnani_api_key',
            'twilio_auth_token',
        ]

        for field in secret_fields:
            if validated_data.get(field):
                validated_data[field] = service._encrypt_credential(validated_data[field])

        instance = super().update(instance, validated_data)

        if request and request.user.is_authenticated:
            instance.updated_by = request.user
            instance.save(update_fields=['updated_by'])

        return instance
class BotCallingProviderHealthLogSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    class Meta:
        model = BotCallingProviderHealthLog
        fields = [
            'id', 'provider', 'provider_name',
            'is_healthy', 'error_message', 'response_time',
            'checked_at', 'created_at', 'updated_at',
            'status', 'test_type',
            'is_deleted', 'deleted_at',
            'created_by', 'updated_by', 'deleted_by',
        ]
        read_only_fields = ['id', 'checked_at', 'created_at', 'updated_at']

class BotCallingProviderUsageLogSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    success_rate = serializers.SerializerMethodField()
    average_response_time = serializers.SerializerMethodField()

    class Meta:
        model = BotCallingProviderUsageLog
        fields = [
            'id', 'provider', 'provider_name',
            'calls_made', 'success_count', 'failure_count',
            'success_rate', 'total_response_time', 'average_response_time',
            'logged_at',
        ]
        read_only_fields = ['id', 'logged_at']

    def get_success_rate(self, obj):
        if obj.calls_made == 0:
            return 0
        return round((obj.success_count / obj.calls_made) * 100, 2)

    def get_average_response_time(self, obj):
        if obj.success_count == 0:
            return 0
        return round(obj.total_response_time / obj.success_count, 3)

class BotCallingProviderTestResultSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tested_by_name = serializers.CharField(source='tested_by.get_full_name', read_only=True)

    class Meta:
        model = BotCallingProviderTestResult
        fields = [
            'id', 'provider', 'provider_name',
            'test_number', 'status', 'status_display',
            'error_message', 'response_time',
            'tested_at', 'tested_by', 'tested_by_name',
        ]
        read_only_fields = ['id', 'tested_at']

class BotCallingProviderTestSerializer(serializers.Serializer):
    test_number = serializers.CharField()

    def validate_test_number(self, value):
        if not value:
            raise serializers.ValidationError("Test phone number is required")
        return value

class BotCallingProviderStatsSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()
    provider_name = serializers.CharField()
    provider_type = serializers.CharField()
    is_active = serializers.BooleanField()
    status = serializers.CharField()
    calls_made_today = serializers.IntegerField()
    calls_made_this_month = serializers.IntegerField()
    daily_limit = serializers.IntegerField()
    monthly_limit = serializers.IntegerField()
    daily_usage_percentage = serializers.FloatField()
    monthly_usage_percentage = serializers.FloatField()
    last_health_check = serializers.DateTimeField(allow_null=True)
    success_rate = serializers.FloatField()
    average_response_time = serializers.FloatField()