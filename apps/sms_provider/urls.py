from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SmsProviderViewSet, SmsMessageViewSet, TwilioWebhookView # <--- Import the view
router = DefaultRouter()
router.register(r'providers', SmsProviderViewSet, basename='sms-provider')
router.register(r'messages', SmsMessageViewSet, basename='sms-message')
app_name = 'sms_provider'
urlpatterns = [
    path('', include(router.urls)),
    
    # --- NEW WEBHOOK PATH ---
    path('webhook/twilio/', TwilioWebhookView.as_view(), name='twilio-webhook'),
]