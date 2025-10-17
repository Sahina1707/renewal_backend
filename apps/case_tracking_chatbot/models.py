from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
import uuid
from django.utils import timezone

User = get_user_model()

class CaseTrackingChatbotConversation(BaseModel):
    """Model to store conversation history for the case tracking chatbot."""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='case_tracking_chatbot_conversations', 
        null=True, 
        blank=True
    )
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    title = models.CharField(max_length=255, blank=True, help_text="A brief title for the conversation")
    last_activity = models.DateTimeField(auto_now=True, db_index=True)
    message_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, 
        default='active', 
        db_index=True,
        choices=[
            ('active', 'Active'),
            ('archived', 'Archived'),
            ('deleted', 'Deleted')
        ]
    )
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'case_tracking_chat_conversations'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['session_id']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return self.title or f"Conversation {self.session_id}"
    
    def update_message_count(self):
        self.message_count = self.messages.count()
        self.save(update_fields=['message_count'])


class CaseTrackingChatbotMessage(BaseModel):
    """Model to store individual messages within a case tracking chatbot conversation."""
    
    conversation = models.ForeignKey(
        CaseTrackingChatbotConversation, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    role = models.CharField(
        max_length=10, 
        choices=[
            ('user', 'User'), 
            ('assistant', 'Assistant'), 
            ('system', 'System')
        ]
    )
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'case_tracking_chat_messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
