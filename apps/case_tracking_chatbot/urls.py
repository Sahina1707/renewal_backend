from django.urls import path
from apps.case_tracking_chatbot.views import (
    CaseTrackingChatbotView,
    case_tracking_chatbot_quick_suggestions,
    case_tracking_chatbot_conversations,
    case_tracking_chatbot_conversation_detail,
    case_tracking_chatbot_delete_conversation,
    case_tracking_chatbot_status,
)

urlpatterns = [
    path('chat/', CaseTrackingChatbotView.as_view(), name='case_tracking_chatbot_chat'),
    path('suggestions/', case_tracking_chatbot_quick_suggestions, name='case_tracking_chatbot_suggestions'),
    path('conversations/', case_tracking_chatbot_conversations, name='case_tracking_chatbot_conversations'),
    path('conversations/<uuid:conversation_id>/', case_tracking_chatbot_conversation_detail, name='case_tracking_chatbot_conversation_detail'),
    path('conversations/<uuid:conversation_id>/delete/', case_tracking_chatbot_delete_conversation, name='case_tracking_chatbot_delete_conversation'),
    path('status/', case_tracking_chatbot_status, name='case_tracking_chatbot_status'),
]
