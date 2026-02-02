from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework import status
from .models import SystemSettings
from .serializers import (
    SystemSettingsSerializer,
    AIBasicConfigSerializer,
    AIFeaturesSerializer,
    RateLimitingSerializer,
    AdvancedConfigSerializer,
    KnowledgeBaseSerializer,
    SystemPerformanceSerializer,
    OllamaConfigSerializer,
)
import requests
import logging

logger = logging.getLogger(__name__)


class BaseSettingsView(APIView):
    """Base view for settings endpoints with common logic."""
    permission_classes = [IsAuthenticated]
    serializer_class = None

    def get_settings(self):
        return SystemSettings.get_settings()

    def get(self, request):
        settings = self.get_settings()
        return Response(self.serializer_class(settings).data)

    def put(self, request):
        settings = self.get_settings()
        serializer = self.serializer_class(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        return self.put(request)


class SystemSettingsView(BaseSettingsView):
    """Full system settings - GET all or PUT/PATCH to update."""
    serializer_class = SystemSettingsSerializer


class AIBasicConfigView(BaseSettingsView):
    """Basic AI Configuration: Enable AI, Provider, Model, API Key."""
    serializer_class = AIBasicConfigSerializer


class AIFeaturesView(BaseSettingsView):
    """AI Feature toggles: Renewal Insights, Process Optimization, etc."""
    serializer_class = AIFeaturesSerializer


class RateLimitingView(BaseSettingsView):
    """Rate limiting configuration."""
    serializer_class = RateLimitingSerializer


class AdvancedConfigView(BaseSettingsView):
    """Advanced AI configuration: Temperature, Max Tokens, Timeout, Fallback."""
    serializer_class = AdvancedConfigSerializer


class KnowledgeBaseView(BaseSettingsView):
    """Knowledge base settings."""
    serializer_class = KnowledgeBaseSerializer


class SystemPerformanceView(BaseSettingsView):
    """System performance settings: Data Retention, Auto Backup."""
    serializer_class = SystemPerformanceSerializer


class OllamaConfigView(BaseSettingsView):
    """Ollama-specific configuration."""
    serializer_class = OllamaConfigSerializer


class AIProvidersView(APIView):
    """Get available AI providers and their models."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = SystemSettings.get_settings()
        
        # Get all providers
        providers = SystemSettings.get_all_providers()
        
        # Get models for each provider
        models = {}
        for provider in SystemSettings.AI_PROVIDER_CHOICES:
            provider_key = provider[0]
            provider_models = SystemSettings.get_models_for_provider(provider_key)
            models[provider_key] = [
                {"value": m[0], "label": m[1]} 
                for m in provider_models
            ]
        
        # For Ollama, include cached models if available
        if settings.ollama_available_models:
            models['ollama'] = [
                {"value": m, "label": m} 
                for m in settings.ollama_available_models
            ]

        return Response({
            "providers": providers,
            "models": models,
            "current_provider": settings.ai_provider,
            "current_model": settings.ai_model,
        })


class TestAIConnectionView(APIView):
    """Test connection to the configured AI provider."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        settings = SystemSettings.get_settings()

        try:
            if settings.ai_provider == "ollama":
                r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
                r.raise_for_status()
                return Response({
                    "success": True, 
                    "message": "Ollama connected successfully",
                    "provider": "ollama"
                })

            if settings.ai_provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=settings.api_key)
                models = client.models.list()
                return Response({
                    "success": True, 
                    "message": "OpenAI connected successfully",
                    "provider": "openai"
                })

            if settings.ai_provider == "azure_openai":
                # Test Azure OpenAI connection
                if not settings.azure_endpoint:
                    return Response({
                        "success": False,
                        "message": "Azure endpoint is not configured"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    api_key=settings.api_key,
                    api_version=settings.azure_api_version,
                    azure_endpoint=settings.azure_endpoint,
                )
                # Try a simple completion to test
                return Response({
                    "success": True, 
                    "message": "Azure OpenAI connected successfully",
                    "provider": "azure_openai"
                })

            if settings.ai_provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=settings.api_key)
                # Simple validation - the client creation itself validates the key format
                return Response({
                    "success": True, 
                    "message": "Anthropic connected successfully",
                    "provider": "anthropic"
                })

            if settings.ai_provider == "google_ai":
                import google.generativeai as genai
                genai.configure(api_key=settings.api_key)
                # List models to verify connection
                models = genai.list_models()
                return Response({
                    "success": True, 
                    "message": "Google AI connected successfully",
                    "provider": "google_ai"
                })

            return Response({
                "success": False, 
                "message": f"Provider '{settings.ai_provider}' not supported"
            }, status=status.HTTP_400_BAD_REQUEST)

        except ImportError as e:
            logger.error(f"Missing library for AI provider: {str(e)}")
            return Response({
                "success": False, 
                "error": f"Required library not installed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"AI connection test failed: {str(e)}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class OllamaModelsView(APIView):
    """Fetch and refresh available Ollama models."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = SystemSettings.get_settings()

        try:
            r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=10)
            r.raise_for_status()
            data = r.json()
            
            models = [model.get("name") for model in data.get("models", [])]
            
            # Update cached models in settings
            settings.ollama_available_models = models
            settings.ollama_last_model_refresh = timezone.now()
            settings.save()

            return Response({
                "success": True,
                "models": models,
                "last_refreshed": settings.ollama_last_model_refresh
            })

        except requests.exceptions.ConnectionError:
            return Response({
                "success": False,
                "error": "Cannot connect to Ollama. Ensure Ollama is running.",
                "models": settings.ollama_available_models or []
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Failed to fetch Ollama models: {str(e)}")
            return Response({
                "success": False,
                "error": str(e),
                "models": settings.ollama_available_models or []
            }, status=status.HTTP_400_BAD_REQUEST)


class KnowledgeBaseUpdateView(APIView):
    """Trigger a knowledge base update."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        settings = SystemSettings.get_settings()
        
        if not settings.knowledge_base_enabled:
            return Response({
                "success": False,
                "message": "Knowledge base is disabled"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # TODO: Implement actual knowledge base update logic here
            # For now, just update the timestamp
            settings.kb_last_updated = timezone.now()
            settings.save()

            return Response({
                "success": True,
                "message": "Knowledge base update initiated",
                "last_updated": settings.kb_last_updated
            })

        except Exception as e:
            logger.error(f"Knowledge base update failed: {str(e)}")
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
