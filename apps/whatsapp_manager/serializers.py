from rest_framework import serializers
from apps.renewals.models import RenewalCase
from .models import WhatsAppMessage
from apps.templates.models import Template
from django.utils import timezone
# Add these imports
import pytz

# --- 1. Message Serializer (For the Chat Area) ---
class WhatsAppMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField() # <--- Changed to MethodField
    
    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'sender_type', 'sender_name', 'message_type', 
            'content', 'media_url', 'timestamp', 'is_read', 'is_starred'
        ]
        # Tell Django that sender_type, timestamp, etc., are handled by the system
        read_only_fields = ['sender_type', 'sender_name', 'timestamp', 'is_read', 'is_starred']

    def get_sender_name(self, obj):
        # 1. If it is an Agent, show Agent's Name
        if obj.sender_type == 'agent' and obj.sender_user:
            return obj.sender_user.first_name
            
        # 2. If it is a Customer, show the Real Customer Name
        elif obj.sender_type == 'customer':
            try:
                return obj.case.customer.full_name
            except AttributeError:
                return "Unknown Customer"
        # Fallback
        return obj.sender_type.title()

    def get_timestamp(self, obj):
        # Convert UTC to IST (Asia/Kolkata)
        local_tz = pytz.timezone('Asia/Kolkata') 
        local_dt = obj.created_at.astimezone(local_tz)
        return local_dt.strftime("%I:%M %p") # e.g., "03:30 PM"


# --- 2. Chat List Serializer (For the Left Sidebar) ---
class WhatsAppChatListSerializer(serializers.ModelSerializer):
    """
    This serializer formats the RenewalCase as a 'Chat Item' for the sidebar.
    """
    case_id = serializers.CharField(source='case_number', read_only=True)
    
    # Header Info
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    customer_avatar = serializers.CharField(source='customer.avatar', read_only=True, default=None)
    
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    
    # Badges & Status
    status = serializers.CharField(read_only=True) # e.g., "Active", "Payment Completed"
    priority = serializers.CharField(read_only=True)
    
    # Computed Fields (Logic for "Renewed in X days")
    days_left = serializers.SerializerMethodField()
    renewal_date = serializers.DateField(source='policy.end_date', read_only=True)
    
    # Last Message Preview
    last_message = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = RenewalCase
        fields = [
            'case_id', 'customer_name', 'customer_phone', 'customer_avatar',
            'policy_number', 'status', 'priority', 
            'days_left', 'renewal_date',
            'last_message', 'last_message_time', 'unread_count'
        ]

    def get_days_left(self, obj):
        # Calculate days until renewal
        if obj.policy and obj.policy.end_date:
            delta = obj.policy.end_date - timezone.now().date()
            return delta.days
        return 0

    def get_last_message(self, obj):
        last_msg = obj.whatsapp_messages.last()
        if last_msg:
            return last_msg.content[:50] + "..." if len(last_msg.content) > 50 else last_msg.content
        return "Start the conversation..."

    def get_last_message_time(self, obj):
        last_msg = obj.whatsapp_messages.last()
        if last_msg:
            return last_msg.created_at.strftime("%I:%M %p")
        return ""

    def get_unread_count(self, obj):
        # Count messages from customer that are not read
        return obj.whatsapp_messages.filter(sender_type='customer', is_read=False).count()


# --- 3. Start Chat Serializer (For the Modal) ---
class StartNewChatSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    customer_name = serializers.CharField()
    policy_number = serializers.CharField()
    premium_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    renewal_date = serializers.DateField()
    # Remove required=False if it was there. By default, it is REQUIRED.
    initial_message = serializers.CharField(
        required=True, 
        error_messages={"required": "You must send an initial message to start the chat."}
    )

class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = ['id', 'name', 'content']