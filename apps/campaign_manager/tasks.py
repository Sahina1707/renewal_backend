# File: apps/campaign_manager/tasks.py

from celery import shared_task
from django.utils import timezone
from .models import Campaign, SequenceStep, CampaignLog
from apps.audience_manager.models import AudienceContact
from .helpers import send_smtp_email  # Your email sender
import time

@shared_task
def process_campaign(campaign_id):
    """
    Task 1: Starts the campaign.
    Fetches the audience and starts the sequence for each contact.
    """
    print(f"--- CELERY: Processing campaign_id: {campaign_id} ---")
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return f"Campaign {campaign_id} not found."

    # 1. Get Audience & Contacts (using ForeignKey)
    contacts = campaign.audience.contacts.all()

    if not contacts.exists():
        campaign.status = Campaign.CampaignStatus.COMPLETED
        campaign.save()
        return "Campaign has no contacts. Marking complete."

    # 2. Get first step
    # We use the correct related_name 'cm_sequence_steps'
    first_step = campaign.cm_sequence_steps.filter(step_order=1).first()
    if not first_step:
        return "Campaign has no steps."

    # 3. Start the sequence for each contact
    print(f"--- CELERY: Found {contacts.count()} contacts. Starting sequence... ---")
    for contact in contacts:
        # Schedule the next task for this specific contact
        schedule_step_for_contact.delay(
            campaign_id=campaign.id, 
            step_id=first_step.id, 
            contact_id=contact.id
        )
    return f"Campaign {campaign_id} started."


@shared_task
def schedule_step_for_contact(campaign_id, step_id, contact_id):
    """
    Task 2: The "Engine" - Email Only.
    It processes one step for one contact, then schedules the next step.
    """
    try:
        step = SequenceStep.objects.get(id=step_id)
        contact = AudienceContact.objects.get(id=contact_id)
        campaign = Campaign.objects.get(id=campaign_id)
    except Exception as e:
        return f"Could not find models: {e}"

    # --- 1. Check Trigger Condition ---
    if step.trigger_condition == 'no_response':
        has_replied = CampaignLog.objects.filter(
            campaign=campaign,
            contact=contact,
            status=CampaignLog.LogStatus.REPLIED
        ).exists()
        
        if has_replied:
            print(f"--- CELERY: Skipping step {step.step_order} for {contact.id}: User has replied. ---")
            return "Skipped: User replied."

    # --- 2. Get Template (using ForeignKey) ---
    template = step.template
    success = False
    error_msg = None

    # --- 3. Process Channel (EMAIL ONLY) ---
    if step.channel == 'email':
        if contact.email:
            subject = template.subject
            body = template.content
            
            print(f"--- CELERY: Sending email for step {step.step_order} to {contact.email}... ---")
            success, error_msg = send_smtp_email(subject, body, contact.email)
        else:
            error_msg = "Contact has no email."
    else:
        # We ignore other channels for now
        error_msg = f"Skipping channel: {step.channel}"
        print(f"--- CELERY: {error_msg} ---")
        success = True # Mark as "success" to avoid logging a false error

    # --- 4. Log the Result ---
    CampaignLog.objects.create(
        campaign=campaign,
        step=step,
        contact=contact,
        status=CampaignLog.LogStatus.SENT if success else CampaignLog.LogStatus.FAILED,
        sent_at=timezone.now(),
        error_message=error_msg
    )

    # --- 5. Schedule Next Step ---
    next_step = campaign.cm_sequence_steps.filter(
        step_order=step.step_order + 1
    ).first()

    if next_step:
        # This is the "scheduling" part!
        delay_in_seconds = (next_step.delay_days * 86400) + (next_step.delay_hours * 3600)
        
        print(f"--- CELERY: Scheduling next step ({next_step.step_order}) in {delay_in_seconds}s. ---")
        
        schedule_step_for_contact.apply_async(
            args=[campaign_id, next_step.id, contact_id],
            countdown=delay_in_seconds
        )
    else:
        print(f"--- CELERY: End of sequence for contact {contact.id}. ---")

    return "Step completed."