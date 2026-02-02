from django.db import models
from django.contrib.auth.models import User
class CaseLogsChatbot(models.Model):
    case_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the case")
    policy_id = models.CharField(max_length=100, help_text="Policy ID associated with the case")
    customer_id = models.CharField(max_length=100, help_text="Customer ID associated with the case")
    case_type = models.CharField(max_length=50, help_text="Type of case (Renewal, Claim, etc.)")
    case_status = models.CharField(max_length=50, help_text="Current status of the case")
    priority = models.CharField(max_length=20, choices=[
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical')
    ], default='Medium', help_text="Priority level of the case")
    
    chatbot_session_id = models.CharField(max_length=255, unique=True, help_text="Unique session ID for chatbot interaction")
    last_interaction = models.DateTimeField(auto_now=True, help_text="Last time customer interacted with chatbot")
    interaction_count = models.PositiveIntegerField(default=0, help_text="Number of interactions with chatbot")
    is_active = models.BooleanField(default=True, help_text="Whether chatbot is active for this case")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'case_logs_chatbot'
        verbose_name = 'Case Logs Chatbot'
        verbose_name_plural = 'Case Logs Chatbots'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.case_id} - {self.case_type} - {self.case_status}"
class CaseLogsChatbotMessage(models.Model):
    chatbot_session = models.ForeignKey(
        CaseLogsChatbot, 
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
        db_table = 'case_logs_chatbot_messages'
        verbose_name = 'Case Logs Chatbot Message'
        verbose_name_plural = 'Case Logs Chatbot Messages'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.chatbot_session.case_id} - {self.message_type} - {self.timestamp}"
