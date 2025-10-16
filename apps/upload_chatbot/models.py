from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel

User = get_user_model()


class UploadChatbotConversation(BaseModel):
    """Model to store upload chatbot conversation sessions"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='upload_chatbot_conversations',
        help_text="User who initiated this conversation"
    )
    session_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique session identifier for this conversation"
    )
    title = models.CharField(
        max_length=200,
        help_text="Conversation title (auto-generated from first message)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text="Current status of the conversation"
    )
    context_data = models.JSONField(
        default=dict,
        help_text="Additional context data for the conversation"
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this conversation was started"
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp"
    )
    message_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of messages in this conversation"
    )
    
    class Meta:
        db_table = 'upload_chatbot_conversations'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['session_id']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"Upload Chatbot Conversation: {self.title} - {self.user.username}"
    
    def update_message_count(self):
        """Update the message count for this conversation"""
        self.message_count = self.messages.count()
        self.save(update_fields=['message_count'])


class UploadChatbotMessage(BaseModel):
    """Model to store individual messages in upload chatbot conversations"""
    
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(
        UploadChatbotConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Conversation this message belongs to"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        db_index=True,
        help_text="Role of the message sender"
    )
    content = models.TextField(
        help_text="Message content"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata (tokens used, model, etc.)"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this message was sent"
    )
    is_edited = models.BooleanField(
        default=False,
        help_text="Whether this message has been edited"
    )
    
    class Meta:
        db_table = 'upload_chatbot_messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
            models.Index(fields=['role', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
