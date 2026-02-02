from rest_framework import serializers
from .models import SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    """Full system settings serializer."""
    class Meta:
        model = SystemSettings
        fields = "__all__"
        read_only_fields = ("updated_at",)


class AIBasicConfigSerializer(serializers.ModelSerializer):
    """Basic AI Configuration: provider, model, API key."""
    class Meta:
        model = SystemSettings
        fields = [
            "ai_enabled",
            "ai_provider",
            "ai_model",
            "api_key",
        ]


class AIFeaturesSerializer(serializers.ModelSerializer):
    """AI Features toggles."""
    class Meta:
        model = SystemSettings
        fields = [
            "renewal_insights",
            "process_optimization",
            "customer_retention",
            "communication_strategies",
        ]


class RateLimitingSerializer(serializers.ModelSerializer):
    """Rate limiting configuration."""
    class Meta:
        model = SystemSettings
        fields = [
            "rate_limit_enabled",
            "requests_per_minute",
            "requests_per_hour",
        ]


class AdvancedConfigSerializer(serializers.ModelSerializer):
    """Advanced AI configuration."""
    class Meta:
        model = SystemSettings
        fields = [
            "temperature",
            "max_tokens",
            "response_timeout",
            "fallback_enabled",
        ]


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    """Knowledge base settings."""
    class Meta:
        model = SystemSettings
        fields = [
            "knowledge_base_enabled",
            "kb_auto_update",
            "kb_last_updated",
        ]
        read_only_fields = ("kb_last_updated",)


class SystemPerformanceSerializer(serializers.ModelSerializer):
    """System performance settings."""
    class Meta:
        model = SystemSettings
        fields = [
            "data_retention_period",
            "auto_backup",
        ]


class OllamaConfigSerializer(serializers.ModelSerializer):
    """Ollama-specific configuration."""
    class Meta:
        model = SystemSettings
        fields = [
            "ollama_base_url",
            "ollama_model",
            "ollama_keep_alive",
            "ollama_stream",
            "ollama_system_prompt",
            "ollama_options",
            "ollama_available_models",
            "ollama_last_model_refresh",
        ]
        read_only_fields = ("ollama_available_models", "ollama_last_model_refresh")


class AIProviderSerializer(serializers.Serializer):
    """Serializer for AI provider options."""
    value = serializers.CharField()
    label = serializers.CharField()


class AIModelSerializer(serializers.Serializer):
    """Serializer for AI model options."""
    value = serializers.CharField()
    label = serializers.CharField()


class AIProvidersResponseSerializer(serializers.Serializer):
    """Response serializer for available providers and models."""
    providers = AIProviderSerializer(many=True)
    models = serializers.DictField(child=AIModelSerializer(many=True))
    current_provider = serializers.CharField()
    current_model = serializers.CharField(allow_null=True)
