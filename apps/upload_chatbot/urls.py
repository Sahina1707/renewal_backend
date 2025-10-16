from django.urls import path
from apps.upload_chatbot.views import (
    UploadChatbotView,
    upload_chatbot_quick_suggestions,
    upload_chatbot_conversations,
    upload_chatbot_conversation_detail,
    upload_chatbot_delete_conversation,
    upload_chatbot_status
)

app_name = 'upload_chatbot'

urlpatterns = [
    # Main chatbot endpoint
    path('chat/', UploadChatbotView.as_view(), name='chat'),
    
    # Quick suggestions
    path('suggestions/', upload_chatbot_quick_suggestions, name='quick_suggestions'),
    
    # Conversation management
    path('conversations/', upload_chatbot_conversations, name='conversations'),
    path('conversations/<int:conversation_id>/', upload_chatbot_conversation_detail, name='conversation_detail'),
    path('conversations/<int:conversation_id>/delete/', upload_chatbot_delete_conversation, name='delete_conversation'),
    
    # Service status
    path('status/', upload_chatbot_status, name='status'),
]
