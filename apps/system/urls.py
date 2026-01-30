from django.urls import path
from .views import (
    SystemSettingsView,
    AIBasicConfigView,
    AIFeaturesView,
    RateLimitingView,
    AdvancedConfigView,
    KnowledgeBaseView,
    KnowledgeBaseUpdateView,
    SystemPerformanceView,
    OllamaConfigView,
    TestAIConnectionView,
    OllamaModelsView,
    AIProvidersView,
)

urlpatterns = [
    # Full settings
    path("settings/", SystemSettingsView.as_view(), name="system-settings"),
    
    # AI Providers and Models (dropdown options)
    path("ai-providers/", AIProvidersView.as_view(), name="ai-providers"),
    
    # Basic AI Configuration
    path("ai-config/", AIBasicConfigView.as_view(), name="ai-basic-config"),
    
    # AI Features
    path("ai-features/", AIFeaturesView.as_view(), name="ai-features"),
    
    # Rate Limiting
    path("rate-limiting/", RateLimitingView.as_view(), name="rate-limiting"),
    
    # Advanced Configuration
    path("advanced-config/", AdvancedConfigView.as_view(), name="advanced-config"),
    
    # Knowledge Base
    path("knowledge-base/", KnowledgeBaseView.as_view(), name="knowledge-base"),
    path("knowledge-base", KnowledgeBaseView.as_view(), name="knowledge-base-no-slash"),
    path("knowledge-base/update/", KnowledgeBaseUpdateView.as_view(), name="knowledge-base-update"),
    
    # System Performance
    path("performance/", SystemPerformanceView.as_view(), name="system-performance"),
    
    # Ollama Configuration
    path("ollama-config/", OllamaConfigView.as_view(), name="ollama-config"),
    path("ollama-models/", OllamaModelsView.as_view(), name="ollama-models"),
    
    # Connection Testing
    path("test-connection/", TestAIConnectionView.as_view(), name="test-ai-connection"),
]
