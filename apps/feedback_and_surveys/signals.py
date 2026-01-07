from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SurveySubmission
from apps.feedback_settings.models import SurveySettings 
from apps.email_provider.services import EmailProviderService 
from apps.feedback_and_surveys.models import AutomationTrigger
from apps.feedback_and_surveys.services import DistributionService
from apps.policies.models import Policy, PolicyClaim 

@receiver(post_save, sender=Policy)
def trigger_policy_survey(sender, instance, created, **kwargs):
    """
    When a NEW Policy is created, check if we need to send a survey.
    """
    if created: 
        triggers = AutomationTrigger.objects.filter(event_type='policy_purchased', is_active=True)
        
        for trigger in triggers:
            service = DistributionService(trigger.survey)
            if instance.customer:
                service.send_transactional(instance.customer, channels=trigger.channels)
@receiver(post_save, sender=PolicyClaim)
def trigger_claim_survey(sender, instance, created, **kwargs):
    """
    When a Claim status changes to 'closed' or 'paid', send a survey.
    """
    if instance.status in ['closed', 'paid']: 
        
        triggers = AutomationTrigger.objects.filter(event_type='claim_settled', is_active=True)
        
        for trigger in triggers:
            service = DistributionService(trigger.survey)
            customer = None
            if instance.policy and instance.policy.customer:
                customer = instance.policy.customer
            
            if customer:
                service.send_transactional(customer, channels=trigger.channels)