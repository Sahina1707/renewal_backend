from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmailWebhookViewSet,
    EmailAutomationViewSet,
    EmailAutomationLogViewSet,
    EmailIntegrationViewSet,
    EmailSLAViewSet,
    EmailTemplateVariableViewSet,
    EmailIntegrationAnalyticsViewSet,
    sendgrid_incoming_webhook,
    sendgrid_events_webhook
)

router = DefaultRouter()
router.register(r'webhooks', EmailWebhookViewSet, basename='email-webhook')
router.register(r'automations', EmailAutomationViewSet, basename='email-automation')
router.register(r'automation-logs', EmailAutomationLogViewSet, basename='email-automation-log')
router.register(r'integrations', EmailIntegrationViewSet, basename='email-integration')
router.register(r'slas', EmailSLAViewSet, basename='email-sla')
router.register(r'template-variables', EmailTemplateVariableViewSet, basename='email-template-variable')
router.register(r'analytics', EmailIntegrationAnalyticsViewSet, basename='email-integration-analytics')

urlpatterns = [
    path('', include(router.urls)),
    path('webhooks/sendgrid/incoming/', sendgrid_incoming_webhook, name='sendgrid-incoming-webhook'),
    path('webhooks/sendgrid/events/', sendgrid_events_webhook, name='sendgrid-events-webhook'),
]
