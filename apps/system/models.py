from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class SystemSettings(models.Model):
    """Global system settings - singleton pattern (only one row with pk=1)."""
    
    # AI Provider Choices
    AI_PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('azure_openai', 'Azure OpenAI'),
        ('anthropic', 'Anthropic'),
        ('google_ai', 'Google AI'),
        ('ollama', 'Ollama (Local)'),
    ]
    
    # AI Model Choices per Provider
    AI_MODEL_CHOICES = {
        'openai': [
            ('gpt-4', 'GPT-4'),
            ('gpt-4-turbo', 'GPT-4 Turbo'),
            ('gpt-4o', 'GPT-4o'),
            ('gpt-4o-mini', 'GPT-4o Mini'),
            ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ],
        'azure_openai': [
            ('gpt-4', 'GPT-4'),
            ('gpt-4-turbo', 'GPT-4 Turbo'),
            ('gpt-35-turbo', 'GPT-3.5 Turbo'),
        ],
        'anthropic': [
            ('claude-3-opus', 'Claude 3 Opus'),
            ('claude-3-sonnet', 'Claude 3 Sonnet'),
            ('claude-3-haiku', 'Claude 3 Haiku'),
            ('claude-2.1', 'Claude 2.1'),
            ('claude-2', 'Claude 2'),
        ],
        'google_ai': [
            ('gemini-pro', 'Gemini Pro'),
            ('gemini-pro-vision', 'Gemini Pro Vision'),
            ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
            ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
        ],
        'ollama': [],  # Dynamic based on installed models
    }

    # ========= BASIC AI =========
    ai_enabled = models.BooleanField(default=False, help_text="Enable AI-powered assistance")
    ai_provider = models.CharField(
        max_length=50, 
        choices=AI_PROVIDER_CHOICES,
        default="openai",
        help_text="Select the AI service provider"
    )
    ai_model = models.CharField(max_length=100, blank=True, null=True, help_text="Select the AI model to use")
    api_key = models.TextField(blank=True, null=True, help_text="Enter your AI provider API key")

    # ========= AZURE OPENAI SPECIFIC =========
    azure_endpoint = models.URLField(blank=True, null=True, help_text="Azure OpenAI endpoint URL")
    azure_deployment_name = models.CharField(max_length=100, blank=True, null=True, help_text="Azure deployment name")
    azure_api_version = models.CharField(max_length=20, default="2024-02-01", help_text="Azure API version")

    # ========= GOOGLE AI SPECIFIC =========
    google_project_id = models.CharField(max_length=100, blank=True, null=True, help_text="Google Cloud Project ID")

    # ========= ADVANCED =========
    temperature = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Controls response creativity (0.0 - 1.0)"
    )
    max_tokens = models.PositiveIntegerField(default=1000, help_text="Maximum response length")
    response_timeout = models.PositiveIntegerField(default=30, help_text="Request timeout in seconds")
    fallback_enabled = models.BooleanField(default=True, help_text="Show fallback message when AI is unavailable")

    # ========= FEATURES =========
    renewal_insights = models.BooleanField(default=True)
    process_optimization = models.BooleanField(default=True)
    customer_retention = models.BooleanField(default=True)
    communication_strategies = models.BooleanField(default=True)

    # ========= RATE LIMIT =========
    rate_limit_enabled = models.BooleanField(default=True, help_text="Prevent API quota exhaustion")
    requests_per_minute = models.PositiveIntegerField(default=60, help_text="Maximum requests per minute")
    requests_per_hour = models.PositiveIntegerField(default=1000, help_text="Maximum requests per hour")

    # ========= KNOWLEDGE BASE =========
    knowledge_base_enabled = models.BooleanField(default=True, help_text="Use internal knowledge for better responses")
    kb_auto_update = models.BooleanField(default=True, help_text="Automatically update knowledge base")
    kb_last_updated = models.DateTimeField(null=True, blank=True)

    # ========= OLLAMA =========
    ollama_base_url = models.URLField(
        default="http://localhost:11434",
        blank=True,
        help_text="Ollama server URL"
    )
    ollama_model = models.CharField(max_length=100, blank=True, null=True)
    ollama_keep_alive = models.CharField(max_length=20, default="5m")
    ollama_stream = models.BooleanField(default=False)
    ollama_system_prompt = models.TextField(blank=True, null=True)
    ollama_options = models.JSONField(default=dict, blank=True)
    ollama_available_models = models.JSONField(default=list, blank=True)
    ollama_last_model_refresh = models.DateTimeField(null=True, blank=True)

    # ========= SYSTEM =========
    data_retention_period = models.PositiveIntegerField(default=12, help_text="How long to keep archived data (months)")
    auto_backup = models.BooleanField(default=True, help_text="Automatically backup data to cloud storage")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion

    @staticmethod
    def get_settings():
        obj, _ = SystemSettings.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def get_models_for_provider(cls, provider):
        """Get available AI models for a specific provider."""
        return cls.AI_MODEL_CHOICES.get(provider, [])

    @classmethod
    def get_all_providers(cls):
        """Get list of all available AI providers."""
        return [
            {"value": choice[0], "label": choice[1]} 
            for choice in cls.AI_PROVIDER_CHOICES
        ]

    def __str__(self):
        return "Global System Settings"
