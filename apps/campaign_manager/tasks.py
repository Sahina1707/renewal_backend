from celery import shared_task
from django.utils import timezone
from datetime import timedelta 
from .models import Campaign, SequenceStep, CampaignLog, PendingTask 
from apps.email_provider.services import EmailProviderService
from apps.email_provider.models import EmailProviderConfig
from apps.audience_manager.models import AudienceContact
from apps.whatsapp_provider.services import WhatsAppService, WhatsAppAPIError
from apps.whatsapp_provider.models import WhatsAppMessageTemplate, WhatsAppProvider
from apps.sms_provider.services import SmsService, SmsApiException
import time

@shared_task(name="check_scheduled_campaigns")
def check_scheduled_campaigns():
    now = timezone.now()
    
    campaigns_to_start = Campaign.objects.filter(
        status=Campaign.CampaignStatus.SCHEDULED, 
        scheduled_date__lte=now,
        is_deleted=False
    )
    
    print(f"--- CELERY BEAT: Found {campaigns_to_start.count()} campaigns to start. ---")

    for campaign in campaigns_to_start:
        campaign.status = Campaign.CampaignStatus.ACTIVE
        campaign.save()
        process_campaign.delay(campaign_id=campaign.id)
        
    return f"Started {campaigns_to_start.count()} scheduled campaigns."

@shared_task
def process_campaign(campaign_id):
    print(f"--- CELERY: Processing new campaign_id: {campaign_id} ---")
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return f"Campaign {campaign_id} not found."
    if campaign.enable_email and not campaign.email_provider:
        default_provider = EmailProviderConfig.objects.filter(is_default=True, is_active=True).first()
        if default_provider:
            campaign.email_provider = default_provider
            campaign.save(update_fields=['email_provider'])

    contacts = campaign.audience.contacts.filter(is_deleted=False)    
    if not contacts.exists():
        campaign.status = Campaign.CampaignStatus.COMPLETED
        campaign.save()
        return "Campaign has no contacts. Marking complete."

    first_step = campaign.cm_sequence_steps.filter(step_order=1).first()
    if not first_step:
        campaign.status = Campaign.CampaignStatus.COMPLETED
        campaign.save()
        return "Campaign has no steps. Marking complete."

    print(f"--- CELERY: Found {contacts.count()} contacts. Starting sequence... ---")
    for contact in contacts:
        schedule_step_for_contact.apply_async(
            args=[campaign.id, first_step.id, contact.id],
            countdown=5 
        )
    return f"Campaign {campaign_id} started."


@shared_task
def resume_paused_campaign(campaign_id):
    print(f"--- CELERY: Resuming paused campaign_id: {campaign_id} ---")
    tasks_to_resume = PendingTask.objects.filter(campaign_id=campaign_id)
    
    if not tasks_to_resume.exists():
        return "No pending tasks found to resume."

    now = timezone.now()
    resumed_count = 0
    
    for task in tasks_to_resume:
        delay_seconds = 0
        if task.scheduled_for > now:
            delay_seconds = (task.scheduled_for - now).total_seconds()
        
        schedule_step_for_contact.apply_async(
            args=[task.campaign_id, task.step_id, task.contact_id],
            countdown=delay_seconds
        )
        resumed_count += 1
    tasks_to_resume.delete()
    return f"Resumed {resumed_count} tasks for campaign {campaign_id}."

@shared_task(bind=True)
def schedule_step_for_contact(self, campaign_id, step_id, contact_id):
    PendingTask.objects.filter(task_id=self.request.id).delete()
    
    try:
        step = SequenceStep.objects.get(id=step_id)
        contact = AudienceContact.objects.get(id=contact_id)
        campaign = Campaign.objects.get(id=campaign_id)
    except Exception as e:
        return f"Could not find models: {e}"

    if campaign.status == Campaign.CampaignStatus.PAUSED:
        print(f"--- CELERY: Campaign is PAUSED. Re-queueing task. ---")
        PendingTask.objects.get_or_create(
            task_id=self.request.id,
            defaults={
                'campaign': campaign,
                'contact': contact,
                'step': step,
                'scheduled_for': timezone.now() 
            }
        )
        return "Campaign paused. Task stored."
    
    if campaign.status == Campaign.CampaignStatus.COMPLETED:
        return "Campaign is completed. Skipping."
    if step.trigger_condition in ['no_response', 'no_action']:
        has_interacted = CampaignLog.objects.filter(
            campaign=campaign,
            contact=contact,
            status__in=[
                CampaignLog.LogStatus.REPLIED, 
                CampaignLog.LogStatus.CLICKED
            ]
        ).exists()
        
        if has_interacted:
            print(f"--- CELERY: Skipping step {step.step_order} for {contact.id}: User has replied/clicked. ---")
            return "Skipped: User interacted."
    template = step.template
    success = False
    error_msg = None
    message_id = None 

    if step.channel == 'email' and campaign.enable_email:
        if contact.email:
            print(f"--- CELERY: Sending email for step {step.step_order} to {contact.email}... ---")
            provider = getattr(campaign, 'email_provider', None)
            
            if not provider:
                provider = EmailProviderConfig.objects.filter(is_default=True, is_active=True).first()
            if provider:
                try:
                    email_service = EmailProviderService(config=provider)
                    
                    rendered_content = template.content 
                    
                    result = email_service.send_email(
                        to_emails=[contact.email],
                        subject=template.subject,
                        html_content=rendered_content,
                        from_email=provider.from_email
                    )
                    
                    success = result.get('success', False)
                    if success:
                        message_id = result.get('message_id', 'sent_via_api')
                    else:
                        error_msg = result.get('error', 'Unknown Error')
                        
                except Exception as e:
                    print(f"🔥 EXCEPTION during send: {e}")
                    success = False
                    error_msg = str(e)
            else:
                error_msg = "No active default provider found."
            
        else:
            error_msg = "Contact has no email."
    
    elif step.channel == 'sms' and campaign.enable_sms:
        if contact.phone:
            body = template.content 
            print(f"--- CELERY: Sending SMS for step {step.step_order} to {contact.phone}... ---")
            success, error_msg, message_id = (True, "SMS sending not implemented", None) 
        else:
            error_msg = "Contact has no phone number."

    elif step.channel == 'whatsapp' and campaign.enable_whatsapp:
        if contact.phone:
            print(f"--- CELERY: Sending Twilio WhatsApp for step {step.step_order} to {contact.phone}... ---")
            try:
                service = WhatsAppService().get_service_instance()

                provider_template = WhatsAppMessageTemplate.objects.get(
                    name=template.name,
                    provider=service.provider,
                    status='approved'
                )
                variable_names = template.variables
                custom_params = []
                for var_name in variable_names:
                    value = getattr(contact, var_name, '')
                    custom_params.append(str(value))

                response = service.send_template_message(
                    to_phone=contact.phone,
                    template=provider_template,
                    template_params=custom_params,
                    campaign=campaign,
                    customer=None 
                )
                success = True
                message_id = response['messages'][0]['id']

            except WhatsAppProvider.DoesNotExist as e:
                success = False
                error_msg = f"No active/default WhatsApp provider configured: {e}"
            except WhatsAppMessageTemplate.DoesNotExist:
                success = False
                error_msg = f"No approved template named '{template.name}' found for the default provider."
            except WhatsAppAPIError as e:
                success = False
                error_msg = str(e)
            except Exception as e:
                success = False
                error_msg = f"A general error occurred: {e}"
        else:
            error_msg = "Contact has no phone number."
    CampaignLog.objects.create(
        campaign=campaign,
        step=step,
        contact=contact,
        status=CampaignLog.LogStatus.SENT if success else CampaignLog.LogStatus.FAILED,
        sent_at=timezone.now(),
        error_message=error_msg,
        message_provider_id=message_id 
    )

    next_step = campaign.cm_sequence_steps.filter(
        step_order=step.step_order + 1
    ).first()

    if next_step and success: 
        delay_in_seconds = (
            (next_step.delay_minutes * 60) +
            (next_step.delay_hours * 3600) +
            (next_step.delay_days * 86400) +
            (next_step.delay_weeks * 604800)
        )
        
        if delay_in_seconds == 0:
            delay_in_seconds = 5 
            
        scheduled_time = timezone.now() + timedelta(seconds=delay_in_seconds)
        
        print(f"--- CELERY: Scheduling next step ({next_step.step_order}) in {delay_in_seconds}s. ---")
        task = schedule_step_for_contact.apply_async(
            args=[campaign_id, next_step.id, contact_id],
            countdown=delay_in_seconds
        )
        PendingTask.objects.create(
            task_id=task.id,
            campaign=campaign,
            contact=contact,
            step=next_step,
            scheduled_for=scheduled_time
        )
        
    elif not next_step:
        print(f"--- CELERY: End of sequence for contact {contact.id}. ---")
    return "Step completed."