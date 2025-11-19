from celery import shared_task
from django.utils import timezone
from datetime import timedelta # <-- NEW
from .models import Campaign, SequenceStep, CampaignLog, PendingTask # <-- UPDATED
from apps.audience_manager.models import AudienceContact
from apps.whatsapp_provider.services import WhatsAppService, WhatsAppAPIError
from apps.whatsapp_provider.models import WhatsAppMessageTemplate, WhatsAppProvider
from .helpers import send_smtp_email
import time

@shared_task(name="check_scheduled_campaigns")
def check_scheduled_campaigns():
    now = timezone.now()
    
    # --- UPDATED ---
    campaigns_to_start = Campaign.objects.filter(
        status=Campaign.CampaignStatus.SCHEDULED, # <-- Find SCHEDULED
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
    """
    Task 1: Starts a NEW campaign (from Draft).
    """
    print(f"--- CELERY: Processing new campaign_id: {campaign_id} ---")
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return f"Campaign {campaign_id} not found."

    contacts = campaign.audience.contacts.all()
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
            countdown=5 # Add 5s buffer
        )
    return f"Campaign {campaign_id} started."


@shared_task
def resume_paused_campaign(campaign_id):
    """
    Task 2: Resumes a PAUSED campaign.
    Finds all pending tasks and re-schedules them.
    """
    print(f"--- CELERY: Resuming paused campaign_id: {campaign_id} ---")
    
    # Find all tasks that were pending when pause was hit
    tasks_to_resume = PendingTask.objects.filter(campaign_id=campaign_id)
    
    if not tasks_to_resume.exists():
        return "No pending tasks found to resume."

    now = timezone.now()
    resumed_count = 0
    
    for task in tasks_to_resume:
        # Calculate new delay
        # If task was scheduled for the future, keep that delay
        # If task was scheduled for the past (i.e., should have run while paused), run it now
        delay_seconds = 0
        if task.scheduled_for > now:
            delay_seconds = (task.scheduled_for - now).total_seconds()
        
        schedule_step_for_contact.apply_async(
            args=[task.campaign_id, task.step_id, task.contact_id],
            countdown=delay_seconds
        )
        resumed_count += 1

    # Clear the old pending tasks
    tasks_to_resume.delete()
    return f"Resumed {resumed_count} tasks for campaign {campaign_id}."


@shared_task(bind=True) # <-- bind=True gives us access to 'self'
def schedule_step_for_contact(self, campaign_id, step_id, contact_id):
    """
    Task 3: The "Engine".
    Processes one step for one contact, then schedules the next.
    """
    # --- NEW: Clear this task from PendingTask DB ---
    # If we are running, we are no longer "pending"
    PendingTask.objects.filter(task_id=self.request.id).delete()
    
    try:
        step = SequenceStep.objects.get(id=step_id)
        contact = AudienceContact.objects.get(id=contact_id)
        campaign = Campaign.objects.get(id=campaign_id)
    except Exception as e:
        return f"Could not find models: {e}"

    # --- 1. Check Campaign Status ---
    if campaign.status == Campaign.CampaignStatus.PAUSED:
        print(f"--- CELERY: Campaign is PAUSED. Re-queueing task. ---")
        # This is a failsafe. We re-add it to the PendingTask list
        # to be picked up by resume_paused_campaign later.
        PendingTask.objects.get_or_create(
            task_id=self.request.id,
            defaults={
                'campaign': campaign,
                'contact': contact,
                'step': step,
                'scheduled_for': timezone.now() # Schedule for "now"
            }
        )
        return "Campaign paused. Task stored."
    
    if campaign.status == Campaign.CampaignStatus.COMPLETED:
        return "Campaign is completed. Skipping."

    # --- 2. Check Trigger Condition (from video 00:51) ---
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

    # --- 3. Process Channel (from video 00:37) ---
    template = step.template
    success = False
    error_msg = None
    message_id = None # <-- NEW

    if step.channel == 'email' and campaign.enable_email:
        if contact.email:
            subject = template.subject
            body = template.content # You must add variable replacement here
            print(f"--- CELERY: Sending email for step {step.step_order} to {contact.email}... ---")
            success, error_msg, message_id = send_smtp_email(subject, body, contact.email)
        else:
            error_msg = "Contact has no email."
    
    elif step.channel == 'sms' and campaign.enable_sms:
        if contact.phone:
            body = template.content # Add variable replacement
            print(f"--- CELERY: Sending SMS for step {step.step_order} to {contact.phone}... ---")
            # success, error_msg, message_id = send_twilio_sms(contact.phone, body)
            success, error_msg, message_id = (True, "SMS sending not implemented", None) # Placeholder
        else:
            error_msg = "Contact has no phone number."

    elif step.channel == 'whatsapp' and campaign.enable_whatsapp:
        if contact.phone:
            print(f"--- CELERY: Sending Twilio WhatsApp for step {step.step_order} to {contact.phone}... ---")
            try:
                # 1. Get the default provider service
                service = WhatsAppService().get_service_instance()

                # 2. Find the provider-specific template matching the campaign template's name
                provider_template = WhatsAppMessageTemplate.objects.get(
                    name=template.name,
                    provider=service.provider,
                    status='approved'
                )

                # 3. Build the template parameters
                variable_names = template.variables
                custom_params = []
                for var_name in variable_names:
                    value = getattr(contact, var_name, '')
                    custom_params.append(str(value))

                # 4. Send the message using the service
                response = service.send_template_message(
                    to_phone=contact.phone,
                    template=provider_template,
                    template_params=custom_params,
                    campaign=campaign,
                    customer=None # Or link to a customer model if you have one
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
    # --- 4. Log the Result ---
    CampaignLog.objects.create(
        campaign=campaign,
        step=step,
        contact=contact,
        status=CampaignLog.LogStatus.SENT if success else CampaignLog.LogStatus.FAILED,
        sent_at=timezone.now(),
        error_message=error_msg,
        message_provider_id=message_id # <-- Store provider ID for webhook
    )

    # --- 5. Schedule Next Step ---
    next_step = campaign.cm_sequence_steps.filter(
        step_order=step.step_order + 1
    ).first()

    if next_step and success: # Only schedule next step if this one didn't fail
        
        # --- UPDATED (from video 00:59) ---
        delay_in_seconds = (
            (next_step.delay_minutes * 60) +
            (next_step.delay_hours * 3600) +
            (next_step.delay_days * 86400) +
            (next_step.delay_weeks * 604800)
        )
        
        if delay_in_seconds == 0:
            delay_in_seconds = 5 # Add 5s buffer for immediate follow-ups
            
        scheduled_time = timezone.now() + timedelta(seconds=delay_in_seconds)
        
        print(f"--- CELERY: Scheduling next step ({next_step.step_order}) in {delay_in_seconds}s. ---")
        
        # Schedule the task
        task = schedule_step_for_contact.apply_async(
            args=[campaign_id, next_step.id, contact_id],
            countdown=delay_in_seconds
        )
        
        # --- NEW (Bug Fix) ---
        # Store the task ID so we can pause it
        PendingTask.objects.create(
            task_id=task.id,
            campaign=campaign,
            contact=contact,
            step=next_step,
            scheduled_for=scheduled_time
        )
        # --- END OF NEW ---
        
    elif not next_step:
        print(f"--- CELERY: End of sequence for contact {contact.id}. ---")
        # Optional: Check if all logs for this campaign are done and mark
        # campaign as COMPLETED.
        
    return "Step completed."