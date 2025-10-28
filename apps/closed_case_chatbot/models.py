from django.db import models
from django.contrib.auth.models import User


class ClosedCaseChatbot(models.Model):
    """
    Model for storing closed case chatbot interactions and data
    """
    case_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the closed case")
    customer_name = models.CharField(max_length=255, help_text="Name of the customer")
    policy_number = models.CharField(max_length=100, help_text="Policy number associated with the case")
    product_name = models.CharField(max_length=255, help_text="Insurance product name")
    category = models.CharField(max_length=50, help_text="Insurance category (Life, Motor, Health, etc.)")
    mobile_number = models.CharField(max_length=15, help_text="Customer mobile number")
    language = models.CharField(max_length=20, default='English', help_text="Preferred language for communication")
    profile_type = models.CharField(max_length=20, choices=[
        ('Normal', 'Normal'),
        ('HNI', 'High Net Worth Individual')
    ], default='Normal', help_text="Customer profile type")
    
    chatbot_session_id = models.CharField(max_length=255, unique=True, help_text="Unique session ID for chatbot interaction")
    last_interaction = models.DateTimeField(auto_now=True, help_text="Last time customer interacted with chatbot")
    interaction_count = models.PositiveIntegerField(default=0, help_text="Number of interactions with chatbot")
    is_active = models.BooleanField(default=True, help_text="Whether chatbot is active for this case")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'closed_case_chatbot'
        verbose_name = 'Closed Case Chatbot'
        verbose_name_plural = 'Closed Case Chatbots'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.case_id} - {self.customer_name}"


class ClosedCaseChatbotMessage(models.Model):
    """
    Model for storing individual chatbot messages and responses
    """
    chatbot_session = models.ForeignKey(
        ClosedCaseChatbot, 
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
        db_table = 'closed_case_chatbot_messages'
        verbose_name = 'Chatbot Message'
        verbose_name_plural = 'Chatbot Messages'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.chatbot_session.case_id} - {self.message_type} - {self.timestamp}"


class ClosedCaseChatbotAnalytics(models.Model):
    """
    Model for storing analytics data about chatbot usage
    """
    chatbot_session = models.ForeignKey(
        ClosedCaseChatbot, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    metric_name = models.CharField(max_length=100, help_text="Name of the metric")
    metric_value = models.FloatField(help_text="Value of the metric")
    metric_date = models.DateField(help_text="Date when metric was recorded")
    
    class Meta:
        db_table = 'closed_case_chatbot_analytics'
        verbose_name = 'Chatbot Analytics'
        verbose_name_plural = 'Chatbot Analytics'
        ordering = ['-metric_date']
    
    def __str__(self):
        return f"{self.chatbot_session.case_id} - {self.metric_name} - {self.metric_date}"
