# whatsapp_flow_management/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppFlowViewSet, 
    FlowAnalyticsReportViewSet,
    WhatsAppMessageTemplateViewSet,
    FlowTemplateViewSet
)

router = DefaultRouter()

# 1. Flow Management APIs
router.register(r'flows', WhatsAppFlowViewSet, basename='whatsapp-flow')

# 2. Analytics APIs
router.register(r'analytics', FlowAnalyticsReportViewSet, basename='flow-analytics')

# 3. Message Templates APIs
router.register(r'message_templates', WhatsAppMessageTemplateViewSet, basename='message-template')

router.register(r'flow_templates', FlowTemplateViewSet, basename='flow-template')

urlpatterns = [
    path('', include(router.urls)),
]