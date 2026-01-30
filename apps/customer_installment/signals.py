from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .services import InstallmentIntegrationService

@receiver(post_save, sender='policies.Policy')
def create_installments_on_policy_creation(sender, instance, created, **kwargs):
    if created:  
        try:
            renewal_case = None
            if hasattr(instance, 'renewal_cases'):
                renewal_case = instance.renewal_cases.first()
            
            result = InstallmentIntegrationService.create_installments_for_policy(
                instance, renewal_case
            )
            
            if result['success']:
                print(f"✅ Created {result['installments_created']} installments for policy {instance.policy_number}")
            else:
                print(f"❌ Failed to create installments for policy {instance.policy_number}: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error in create_installments_on_policy_creation: {str(e)}")


@receiver(post_save, sender='customer_payments.CustomerPayment')
def link_payment_to_installment(sender, instance, created, **kwargs):
    if created: 
        try:
            if instance.payment_status == 'completed':
                result = InstallmentIntegrationService.link_payment_to_installment(instance)
                
                if result['success']:
                    print(f"✅ Payment {instance.transaction_id} linked to installment {result.get('installment_id')}")
                else:
                    print(f"⚠️ Could not link payment {instance.transaction_id}: {result.get('message', 'Unknown error')}")
                    
        except Exception as e:
            print(f"❌ Error in link_payment_to_installment: {str(e)}")


@receiver(post_save, sender='renewals.RenewalCase')
def create_installments_on_renewal_case_creation(sender, instance, created, **kwargs):
    if created:  
        try:
            if hasattr(instance, 'policy') and instance.policy:
                result = InstallmentIntegrationService.create_installments_for_policy(
                    instance.policy, instance
                )
                
                if result['success']:
                    print(f"✅ Created {result['installments_created']} installments for renewal case {instance.case_number}")
                else:
                    print(f"❌ Failed to create installments for renewal case {instance.case_number}: {result.get('error', 'Unknown error')}")
                    
        except Exception as e:
            print(f"❌ Error in create_installments_on_renewal_case_creation: {str(e)}")
