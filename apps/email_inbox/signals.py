from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import EmailInboxMessage
from .serializers import EmailInboxMessageSerializer

@receiver(post_save, sender=EmailInboxMessage)
def broadcast_new_email(sender, instance, created, **kwargs):
    """
    Triggers when a new email is saved to the DB.
    """
    if created and instance.folder.folder_type == 'inbox':
        channel_layer = get_channel_layer()
        
        # Serialize the email data to send to the frontend
        email_data = EmailInboxMessageSerializer(instance).data

        # Send to the "inbox_updates" group
        async_to_sync(channel_layer.group_send)(
            "inbox_updates",
            {
                "type": "inbox_update",
                "event": "new_email",
                "email_data": email_data
            }
        )