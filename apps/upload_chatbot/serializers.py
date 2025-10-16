from rest_framework import serializers
from apps.upload_chatbot.models import UploadChatbotConversation, UploadChatbotMessage


class UploadChatbotMessageSerializer(serializers.ModelSerializer):
    """Serializer for upload chatbot messages"""
    
    class Meta:
        model = UploadChatbotMessage
        fields = [
            'id', 'role', 'content', 'metadata', 'timestamp', 'is_edited'
        ]
        read_only_fields = ['id', 'timestamp']


class UploadChatbotConversationSerializer(serializers.ModelSerializer):
    """Serializer for upload chatbot conversations"""
    
    messages = UploadChatbotMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = UploadChatbotConversation
        fields = [
            'id', 'session_id', 'title', 'status', 'context_data',
            'started_at', 'last_activity', 'message_count', 'messages'
        ]
        read_only_fields = ['id', 'started_at', 'last_activity', 'message_count']
