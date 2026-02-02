from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import CustomerPayment


@receiver(post_save, sender=CustomerPayment)
def update_payment_status_on_save(sender, instance, created, **kwargs):
    try:
        with transaction.atomic():
            status_mapping = {
                'completed': 'success',
                'failed': 'failed',
                'cancelled': 'failed',
                'refunded': 'failed',
                'pending': 'pending',
                'processing': 'pending',
                'partial': 'success',
                'overdue': 'failed',
            }
            
            renewal_payment_status = status_mapping.get(instance.payment_status, 'pending')
            
            if instance.renewal_case:
                instance.renewal_case.payment_status = renewal_payment_status
                instance.renewal_case.save(update_fields=['payment_status'])
                
            if instance.customer:
                latest_payment = CustomerPayment.objects.filter(
                    customer=instance.customer,
                    is_deleted=False
                ).order_by('-payment_date').first()
                
                if latest_payment:
                    customer_payment_status = status_mapping.get(latest_payment.payment_status, 'pending')
                    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating payment status for payment {instance.id}: {str(e)}")


@receiver(post_delete, sender=CustomerPayment)
def update_payment_status_on_delete(sender, instance, **kwargs):
    try:
        with transaction.atomic():
           
            if instance.renewal_case:
              
                remaining_payments = CustomerPayment.objects.filter(
                    renewal_case=instance.renewal_case,
                    is_deleted=False
                ).exclude(id=instance.id)
                
                if remaining_payments.exists():
                   
                    latest_payment = remaining_payments.order_by('-payment_date').first()
                    status_mapping = {
                        'completed': 'success',
                        'failed': 'failed',
                        'cancelled': 'failed',
                        'refunded': 'failed',
                        'pending': 'pending',
                        'processing': 'pending',
                        'partial': 'success',
                        'overdue': 'failed',
                    }
                    renewal_payment_status = status_mapping.get(latest_payment.payment_status, 'pending')
                else:
                 
                    renewal_payment_status = 'pending'
                
                instance.renewal_case.payment_status = renewal_payment_status
                instance.renewal_case.save(update_fields=['payment_status'])
                
    except Exception as e:
      
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating payment status after payment deletion {instance.id}: {str(e)}")


@receiver(pre_save, sender=CustomerPayment)
def update_payment_status_on_soft_delete(sender, instance, **kwargs):
    try:
      
        if instance.pk and instance.is_deleted:
          
            try:
                original = CustomerPayment.objects.get(pk=instance.pk)
                if not original.is_deleted and instance.is_deleted:
                
                    with transaction.atomic():
                        if instance.renewal_case:
                           
                            remaining_payments = CustomerPayment.objects.filter(
                                renewal_case=instance.renewal_case,
                                is_deleted=False
                            ).exclude(id=instance.id)
                            
                            if remaining_payments.exists():
                               
                                latest_payment = remaining_payments.order_by('-payment_date').first()
                                status_mapping = {
                                    'completed': 'success',
                                    'failed': 'failed',
                                    'cancelled': 'failed',
                                    'refunded': 'failed',
                                    'pending': 'pending',
                                    'processing': 'pending',
                                    'partial': 'success',
                                    'overdue': 'failed',
                                }
                                renewal_payment_status = status_mapping.get(latest_payment.payment_status, 'pending')
                            else:
                              
                                renewal_payment_status = 'pending'
                            
                            instance.renewal_case.payment_status = renewal_payment_status
                            instance.renewal_case.save(update_fields=['payment_status'])
                            
            except CustomerPayment.DoesNotExist:
             
                pass
                
    except Exception as e:
     
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating payment status after soft delete {instance.id}: {str(e)}")
