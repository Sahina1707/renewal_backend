from django.db import models
from django.contrib.auth.models import User


class PolicyTimelineChatbot(models.Model):
    """
    Model for storing policy timeline chatbot interactions and data
    """
    customer_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the customer")
    customer_name = models.CharField(max_length=255, help_text="Name of the customer")
    policy_id = models.CharField(max_length=100, help_text="Policy ID associated with the timeline")
    policy_type = models.CharField(max_length=100, help_text="Type of policy (Life, Motor, Health, etc.)")
    policy_premium = models.DecimalField(max_digits=10, decimal_places=2, help_text="Current policy premium")
    policy_start_date = models.DateField(help_text="Policy start date")
    policy_age = models.PositiveIntegerField(help_text="Policy age in years")
    
    chatbot_session_id = models.CharField(max_length=255, unique=True, help_text="Unique session ID for chatbot interaction")
    last_interaction = models.DateTimeField(auto_now=True, help_text="Last time customer interacted with chatbot")
    interaction_count = models.PositiveIntegerField(default=0, help_text="Number of interactions with chatbot")
    is_active = models.BooleanField(default=True, help_text="Whether chatbot is active for this policy timeline")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'policy_timeline_chatbot'
        verbose_name = 'Policy Timeline Chatbot'
        verbose_name_plural = 'Policy Timeline Chatbots'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer_id} - {self.customer_name} - {self.policy_id}"


class PolicyTimelineChatbotMessage(models.Model):
    """
    Model for storing individual chatbot messages and responses
    """
    chatbot_session = models.ForeignKey(
        PolicyTimelineChatbot, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    message_type = models.CharField(max_length=20, choices=[
        ('user', 'User Message'),
        ('bot', 'Bot Response'),
        ('system', 'System Message')
    ], help_text="Type of message")
    content = models.TextField(help_text="Message content")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_helpful = models.BooleanField(null=True, blank=True, help_text="User feedback on message helpfulness")
    
    class Meta:
        db_table = 'policy_timeline_chatbot_messages'
        verbose_name = 'Policy Timeline Chatbot Message'
        verbose_name_plural = 'Policy Timeline Chatbot Messages'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.chatbot_session.customer_id} - {self.message_type} - {self.timestamp}"
