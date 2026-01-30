from django.db import connection
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import EmailInboxMessage, EmailFolder
from .serializers import EmailInboxMessageSerializer


@receiver(post_save, sender=EmailInboxMessage)
def broadcast_new_email(sender, instance, created, **kwargs):
    if created and instance.folder and instance.folder.folder_type in ['inbox', 'sent']:
        channel_layer = get_channel_layer()
        email_data = EmailInboxMessageSerializer(instance).data

        async_to_sync(channel_layer.group_send)(
            "inbox_updates",
            {
                "type": "inbox_update",
                "event": "new_email",
                "email_data": email_data
            }
        )


@receiver(post_migrate)
def create_default_folders(sender, **kwargs):
    """
    Automatically creates the standard system folders after database migration.
    """

    if sender.label != 'email_inbox':
        return

    if EmailFolder._meta.db_table not in connection.introspection.table_names():
        return

    system_folders = [
        ('inbox', 'Inbox'),
        ('sent', 'Sent'),
        ('drafts', 'Drafts'),
        ('trash', 'Trash'),
        ('archive', 'Archive'),
        ('junk', 'Junk'),
    ]

    for folder_type, name in system_folders:
        EmailFolder.objects.get_or_create(
            folder_type=folder_type,
            defaults={
                'name': name,
                'is_system': True
            }
        )

    print("✅ System folders checked/created successfully.")
