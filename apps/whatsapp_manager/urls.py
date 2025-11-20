from django.urls import path
from .views import (
    WhatsAppChatListView, 
    WhatsAppMessageListView, 
    StartNewChatView,
    WhatsAppTemplateListView,
    WhatsAppMessageUpdateView,
    CustomerLookupView,
    TwilioWebhookView 
)

urlpatterns = [
    path('chats/', WhatsAppChatListView.as_view(), name='wa_chat_list'),
    path('chats/<str:case_number>/messages/', WhatsAppMessageListView.as_view(), name='wa_chat_history'),
    path('chats/start-new/', StartNewChatView.as_view(), name='wa_start_new'),
    path('templates/', WhatsAppTemplateListView.as_view(), name='wa_templates'),
    path('lookup-customer/', CustomerLookupView.as_view(), name='wa_customer_lookup'),
    path('messages/<int:id>/', WhatsAppMessageUpdateView.as_view(), name='wa_message_update'),
    path('webhook/twilio/', TwilioWebhookView.as_view(), name='wa_webhook_twilio'),
]