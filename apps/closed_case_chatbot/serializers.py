from rest_framework import serializers
from .models import ClosedCaseChatbot, ClosedCaseChatbotMessage, ClosedCaseChatbotAnalytics

class ClosedCaseChatbotSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = ClosedCaseChatbot
        fields = [
            'id', 'case_id', 'customer_name', 'policy_number', 'product_name',
            'category', 'mobile_number', 'language', 'profile_type',
            'chatbot_session_id', 'last_interaction', 'interaction_count',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_interaction']


class ClosedCaseChatbotMessageSerializer(serializers.ModelSerializer):
   
    chatbot_session_case_id = serializers.CharField(source='chatbot_session.case_id', read_only=True)
    chatbot_session_customer_name = serializers.CharField(source='chatbot_session.customer_name', read_only=True)
    
    class Meta:
        model = ClosedCaseChatbotMessage
        fields = [
            'id', 'chatbot_session', 'chatbot_session_case_id', 'chatbot_session_customer_name',
            'message_type', 'content', 'timestamp', 'is_helpful'
        ]
        read_only_fields = ['id', 'timestamp']


class ClosedCaseChatbotAnalyticsSerializer(serializers.ModelSerializer):
   
    chatbot_session_case_id = serializers.CharField(source='chatbot_session.case_id', read_only=True)
    chatbot_session_customer_name = serializers.CharField(source='chatbot_session.customer_name', read_only=True)
    
    class Meta:
        model = ClosedCaseChatbotAnalytics
        fields = [
            'id', 'chatbot_session', 'chatbot_session_case_id', 'chatbot_session_customer_name',
            'metric_name', 'metric_value', 'metric_date'
        ]
        read_only_fields = ['id']


class ClosedCaseChatbotCreateSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = ClosedCaseChatbot
        fields = [
            'case_id', 'customer_name', 'policy_number', 'product_name',
            'category', 'mobile_number', 'language', 'profile_type'
        ]


class ClosedCaseChatbotMessageCreateSerializer(serializers.ModelSerializer):
      class Meta:
        model = ClosedCaseChatbotMessage
        fields = [
            'chatbot_session', 'message_type', 'content', 'is_helpful'
        ]


class ClosedCaseChatbotAnalyticsCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClosedCaseChatbotAnalytics
        fields = [
            'chatbot_session', 'metric_name', 'metric_value', 'metric_date'
        ]
