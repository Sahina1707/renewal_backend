"""
Utility functions for accessing system settings globally across the project.

Usage in other apps:
    from apps.system.utils import get_system_settings, get_ai_config
    
    settings = get_system_settings()
    if settings.ai_enabled:
        # Use AI features
        pass
"""

from django.core.cache import cache
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

SETTINGS_CACHE_KEY = "global_system_settings"
SETTINGS_CACHE_TIMEOUT = 60  # 1 minute


def get_system_settings():
    """
    Get the global system settings singleton.
    Returns cached version if available, otherwise fetches from DB.
    """
    from .models import SystemSettings
    
    # Try cache first
    settings = cache.get(SETTINGS_CACHE_KEY)
    if settings is not None:
        return settings
    
    # Fetch from DB and cache
    settings = SystemSettings.get_settings()
    cache.set(SETTINGS_CACHE_KEY, settings, SETTINGS_CACHE_TIMEOUT)
    return settings


def invalidate_settings_cache():
    """Invalidate the cached settings. Call this after any settings update."""
    cache.delete(SETTINGS_CACHE_KEY)


def get_ai_config():
    """Get AI-specific configuration as a dictionary."""
    settings = get_system_settings()
    return {
        "enabled": settings.ai_enabled,
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "api_key": settings.api_key,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "response_timeout": settings.response_timeout,
        "fallback_enabled": settings.fallback_enabled,
    }


def get_ollama_config():
    """Get Ollama-specific configuration as a dictionary."""
    settings = get_system_settings()
    return {
        "base_url": settings.ollama_base_url,
        "model": settings.ollama_model,
        "keep_alive": settings.ollama_keep_alive,
        "stream": settings.ollama_stream,
        "system_prompt": settings.ollama_system_prompt,
        "options": settings.ollama_options,
    }


def get_rate_limits():
    """Get rate limiting configuration as a dictionary."""
    settings = get_system_settings()
    return {
        "enabled": settings.rate_limit_enabled,
        "requests_per_minute": settings.requests_per_minute,
        "requests_per_hour": settings.requests_per_hour,
    }


def get_ai_features():
    """Get AI features toggles as a dictionary."""
    settings = get_system_settings()
    return {
        "renewal_insights": settings.renewal_insights,
        "process_optimization": settings.process_optimization,
        "customer_retention": settings.customer_retention,
        "communication_strategies": settings.communication_strategies,
    }


def is_ai_enabled():
    """Quick check if AI is enabled globally."""
    return get_system_settings().ai_enabled


def is_feature_enabled(feature_name):
    """
    Check if a specific AI feature is enabled.
    
    Args:
        feature_name: One of 'renewal_insights', 'process_optimization', 
                     'customer_retention', 'communication_strategies'
    
    Returns:
        bool: True if the feature is enabled, False otherwise
    """
    settings = get_system_settings()
    return getattr(settings, feature_name, False)


def get_knowledge_base_config():
    """Get knowledge base configuration as a dictionary."""
    settings = get_system_settings()
    return {
        "enabled": settings.knowledge_base_enabled,
        "auto_update": settings.kb_auto_update,
        "last_updated": settings.kb_last_updated,
    }


def get_performance_config():
    """Get system performance configuration as a dictionary."""
    settings = get_system_settings()
    return {
        "data_retention_period": settings.data_retention_period,
        "auto_backup": settings.auto_backup,
    }
