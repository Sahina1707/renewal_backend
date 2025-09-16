from rest_framework import serializers
from .models import EmailProviderConfig, EmailProviderHealthLog, EmailProviderUsageLog, EmailProviderTestResult


class EmailProviderConfigSerializer(serializers.ModelSerializer):
    """Serializer for EmailProviderConfig"""
    
    provider_type_display = serializers.CharField(source='get_provider_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    health_status_display = serializers.CharField(source='get_health_status_display', read_only=True)
    
    class Meta:
        model = EmailProviderConfig
        fields = [
            'id', 'name', 'provider_type', 'provider_type_display',
            'api_key', 'api_secret', 'access_key_id', 'secret_access_key',
            'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'smtp_use_tls', 'smtp_use_ssl',
            'from_email', 'from_name', 'reply_to',
            'daily_limit', 'monthly_limit', 'rate_limit_per_minute',
            'priority', 'priority_display', 'is_default', 'is_active',
            'last_health_check', 'health_status', 'health_status_display',
            'emails_sent_today', 'emails_sent_this_month', 'last_reset_daily', 'last_reset_monthly',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'is_deleted', 'deleted_at', 'deleted_by'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'last_health_check', 'health_status', 'emails_sent_today',
            'emails_sent_this_month', 'last_reset_daily', 'last_reset_monthly', 'is_deleted',
            'deleted_at', 'deleted_by'
        ]
    
    def create(self, validated_data):
        """Create a new email provider configuration"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update an email provider configuration"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailProviderConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating EmailProviderConfig (without sensitive fields)"""
    
    class Meta:
        model = EmailProviderConfig
        fields = [
            'name', 'provider_type', 'from_email', 'from_name', 'reply_to',
            'daily_limit', 'monthly_limit', 'rate_limit_per_minute',
            'priority', 'is_default', 'is_active', 'health_check_interval'
        ]
    
    def create(self, validated_data):
        """Create a new email provider configuration"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class EmailProviderConfigUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating EmailProviderConfig"""
    
    class Meta:
        model = EmailProviderConfig
        fields = [
            'name', 'from_email', 'from_name', 'reply_to',
            'daily_limit', 'monthly_limit', 'rate_limit_per_minute',
            'priority', 'is_default', 'is_active', 'health_check_interval'
        ]
    
    def update(self, instance, validated_data):
        """Update an email provider configuration"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailProviderCredentialsSerializer(serializers.ModelSerializer):
    """Serializer for updating email provider credentials"""
    
    class Meta:
        model = EmailProviderConfig
        fields = [
            'api_key', 'api_secret', 'access_key_id', 'secret_access_key',
            'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'smtp_use_tls', 'smtp_use_ssl'
        ]
    
    def update(self, instance, validated_data):
        """Update email provider credentials"""
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class EmailProviderHealthLogSerializer(serializers.ModelSerializer):
    """Serializer for EmailProviderHealthLog"""
    
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    
    class Meta:
        model = EmailProviderHealthLog
        fields = [
            'id', 'provider', 'provider_name', 'is_healthy', 'error_message',
            'response_time', 'checked_at'
        ]
        read_only_fields = ['id', 'checked_at']


class EmailProviderUsageLogSerializer(serializers.ModelSerializer):
    """Serializer for EmailProviderUsageLog"""
    
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    success_rate = serializers.SerializerMethodField()
    average_response_time = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailProviderUsageLog
        fields = [
            'id', 'provider', 'provider_name', 'emails_sent', 'success_count',
            'failure_count', 'success_rate', 'total_response_time',
            'average_response_time', 'logged_at'
        ]
        read_only_fields = ['id', 'logged_at']
    
    def get_success_rate(self, obj):
        """Calculate success rate percentage"""
        if obj.emails_sent == 0:
            return 0
        return round((obj.success_count / obj.emails_sent) * 100, 2)
    
    def get_average_response_time(self, obj):
        """Calculate average response time"""
        if obj.success_count == 0:
            return 0
        return round(obj.total_response_time / obj.success_count, 3)


class EmailProviderTestResultSerializer(serializers.ModelSerializer):
    """Serializer for EmailProviderTestResult"""
    
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tested_by_name = serializers.CharField(source='tested_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmailProviderTestResult
        fields = [
            'id', 'provider', 'provider_name', 'test_email', 'status',
            'status_display', 'error_message', 'response_time', 'tested_at',
            'tested_by', 'tested_by_name'
        ]
        read_only_fields = ['id', 'tested_at']


class EmailProviderTestSerializer(serializers.Serializer):
    """Serializer for testing email provider configuration"""
    
    test_email = serializers.EmailField()
    
    def validate_test_email(self, value):
        """Validate test email address"""
        if not value:
            raise serializers.ValidationError("Test email is required")
        return value


class EmailProviderStatsSerializer(serializers.Serializer):
    """Serializer for email provider statistics"""
    
    provider_id = serializers.UUIDField()
    provider_name = serializers.CharField()
    provider_type = serializers.CharField()
    is_active = serializers.BooleanField()
    health_status = serializers.CharField()
    emails_sent_today = serializers.IntegerField()
    emails_sent_this_month = serializers.IntegerField()
    daily_limit = serializers.IntegerField()
    monthly_limit = serializers.IntegerField()
    daily_usage_percentage = serializers.FloatField()
    monthly_usage_percentage = serializers.FloatField()
    last_health_check = serializers.DateTimeField()
    success_rate = serializers.FloatField()
    average_response_time = serializers.FloatField()
