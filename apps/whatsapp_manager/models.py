from django.db import models
from apps.core.models import BaseModel
from apps.renewals.models import RenewalCase
from django.contrib.auth import get_user_model

User = get_user_model()

class WhatsAppMessage(BaseModel):
    """
    Individual chat messages linked to a Renewal Case.
    """
    SENDER_CHOICES = [
        ('agent', 'Agent'),
        ('customer', 'Customer'),
        ('system', 'System'),
    ]

    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('template', 'Template'),
        ('image', 'Image'),
        ('document', 'Document'),
    ]

    case = models.ForeignKey(
        RenewalCase, 
        on_delete=models.CASCADE, 
        related_name='whatsapp_messages'
    )
    
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    sender_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # If agent sent it
    
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField(help_text="Text content or Template Name")
    media_url = models.URLField(null=True, blank=True, help_text="For images/docs")
    
    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False, help_text="Star this message in the UI")
    wa_message_id = models.CharField(max_length=100, null=True, blank=True, help_text="WhatsApp API Message ID")
    
    class Meta:
        db_table = 'whatsapp_manager_messages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.case.case_number} - {self.sender_type}: {self.content[:20]}"