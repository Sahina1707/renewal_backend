from rest_framework import serializers
from apps.case_tracking_chatbot.models import (
    CaseTrackingChatbotConversation,
    CaseTrackingChatbotMessage
)

class CaseTrackingChatbotMessageSerializer(serializers.ModelSerializer):
    """Serializer for CaseTrackingChatbotMessage"""
    
    class Meta:
        model = CaseTrackingChatbotMessage
        fields = [
            'id', 'conversation', 'role', 'content', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CaseTrackingChatbotConversationSerializer(serializers.ModelSerializer):
    """Serializer for CaseTrackingChatbotConversation"""
    
    messages = CaseTrackingChatbotMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = CaseTrackingChatbotConversation
        fields = [
            'id', 'user', 'session_id', 'title', 'last_activity',
            'message_count', 'status', 'metadata', 'messages',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'session_id', 'last_activity', 'message_count',
            'created_at', 'updated_at'
        ]
