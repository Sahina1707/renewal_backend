from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SmsProviderViewSet, SmsMessageViewSet, SmsWebhookView
router = DefaultRouter()
router.register(r'providers', SmsProviderViewSet, basename='sms-provider')
router.register(r'messages', SmsMessageViewSet, basename='sms-message')
app_name = 'sms_provider'
urlpatterns = [
    path('', include(router.urls)),
    
    path('webhook/<str:provider_type>/', SmsWebhookView.as_view(), name='sms-webhook'),
]