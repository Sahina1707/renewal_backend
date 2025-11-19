from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppProviderViewSet,
    WhatsAppPhoneNumberViewSet,
    WhatsAppMessageTemplateViewSet,
    WhatsAppMessageViewSet,
    WhatsAppWebhookEventViewSet,
    WhatsAppFlowViewSet,
    WhatsAppWebhookView,
    WhatsAppAnalyticsViewSet,
)

# Create router for API endpoints
router = DefaultRouter()
router.register(r'providers', WhatsAppProviderViewSet, basename='whatsapp-provider')
router.register(r'phone-numbers', WhatsAppPhoneNumberViewSet, basename='whatsapp-phone-numbers')
router.register(r'templates', WhatsAppMessageTemplateViewSet, basename='whatsapp-templates')
router.register(r'messages', WhatsAppMessageViewSet, basename='whatsapp-messages')
router.register(r'webhook-events', WhatsAppWebhookEventViewSet, basename='whatsapp-webhook-events')
router.register(r'flows', WhatsAppFlowViewSet, basename='whatsapp-flows')
router.register(r'analytics', WhatsAppAnalyticsViewSet, basename='whatsapp-analytics')

app_name = 'whatsapp_provider'

urlpatterns = [
    path('', include(router.urls)),
    path(
        'webhook/<int:provider_id>/', 
        WhatsAppWebhookView.as_view({'get': 'verify_webhook', 'post': 'handle_webhook'}), 
        name='whatsapp-webhook'
    ),
]