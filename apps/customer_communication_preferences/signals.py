from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from .models import CommunicationLog


@receiver(post_save, sender=CommunicationLog)
def update_last_contact_date_on_save(sender, instance, created, **kwargs):
    try:
        with transaction.atomic():
            if instance.customer:
                latest_communication = CommunicationLog.objects.filter(
                    customer=instance.customer,
                    is_deleted=False
                ).order_by('-communication_date').first()
                
                if latest_communication:
                    instance.customer.last_contact_date = latest_communication.communication_date
                    instance.customer.save(update_fields=['last_contact_date'])
                else:
                    instance.customer.last_contact_date = None
                    instance.customer.save(update_fields=['last_contact_date'])
                    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating last_contact_date for customer {instance.customer.id}: {str(e)}")


@receiver(post_delete, sender=CommunicationLog)
def update_last_contact_date_on_delete(sender, instance, **kwargs):
    try:
        with transaction.atomic():
            if instance.customer:
                remaining_communications = CommunicationLog.objects.filter(
                    customer=instance.customer,
                    is_deleted=False
                ).exclude(id=instance.id)
                
                if remaining_communications.exists():
                    latest_communication = remaining_communications.order_by('-communication_date').first()
                    instance.customer.last_contact_date = latest_communication.communication_date
                else:
                    instance.customer.last_contact_date = None
                
                instance.customer.save(update_fields=['last_contact_date'])
                
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating last_contact_date after communication deletion {instance.id}: {str(e)}")


@receiver(pre_save, sender=CommunicationLog)
def update_last_contact_date_on_soft_delete(sender, instance, **kwargs):
    try:
        if instance.pk and instance.is_deleted:
            try:
                original = CommunicationLog.objects.get(pk=instance.pk)
                if not original.is_deleted and instance.is_deleted:
                    with transaction.atomic():
                        if instance.customer:
                            remaining_communications = CommunicationLog.objects.filter(
                                customer=instance.customer,
                                is_deleted=False
                            ).exclude(id=instance.id)
                            
                            if remaining_communications.exists():
                                latest_communication = remaining_communications.order_by('-communication_date').first()
                                instance.customer.last_contact_date = latest_communication.communication_date
                            else:
                                instance.customer.last_contact_date = None
                            
                            instance.customer.save(update_fields=['last_contact_date'])
                            
            except CommunicationLog.DoesNotExist:
                pass
                
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating last_contact_date after soft delete {instance.id}: {str(e)}")