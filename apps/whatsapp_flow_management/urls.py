from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppFlowViewSet, 
    FlowAnalyticsReportViewSet,
    WhatsAppMessageTemplateViewSet,
    FlowTemplateViewSet,
    AITemplateViewSet,
    TemplatesDashboardViewSet,
    AnalyticsDashboardViewSet
)

router = DefaultRouter()
router.register(r'message_templates', WhatsAppMessageTemplateViewSet, basename='message-template')
router.register(r'flow_templates', FlowTemplateViewSet, basename='flow-template')
router.register(r'ai_templates', AITemplateViewSet, basename='ai-templates')
router.register(r'flows', WhatsAppFlowViewSet, basename='whatsapp-flow')
router.register(r'analytics', FlowAnalyticsReportViewSet, basename='flow-analytics')
router.register(r'templates_dashboard', TemplatesDashboardViewSet, basename='templates_dashboard')
router.register(r'analytics_dashboard', AnalyticsDashboardViewSet, basename='analytics_dashboard')
urlpatterns = [
    path('', include(router.urls)),
]