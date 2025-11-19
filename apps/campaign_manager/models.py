# File: apps/campaign_manager/models.py

from django.db import models
from django.utils import timezone
from apps.users.models import User 
from apps.audience_manager.models import Audience, AudienceContact
from apps.templates.models import Template

# --- 2. CAMPAIGN MODEL ---
class Campaign(models.Model):
    class CampaignTypes(models.TextChoices):
        PROMOTIONAL = 'promotional', 'Promotional'
        RENEWAL = 'renewal', 'Renewal'
        # --- NEW (from video) ---
        WELCOME = 'welcome', 'Welcome' 
    
    class CampaignStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        SCHEDULED = 'scheduled', 'Scheduled' # <-- NEW

    name = models.CharField(max_length=255)
    # --- NEW (from video 00:27) ---
    description = models.TextField(blank=True, null=True)
    
    campaign_type = models.CharField(max_length=20, choices=CampaignTypes.choices)
    status = models.CharField(max_length=10, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)
    
    audience = models.ForeignKey(
        Audience, 
        on_delete=models.PROTECT,
        related_name="cm_campaigns"
    )
    scheduled_date = models.DateTimeField(null=True, blank=True)
    
    enable_email = models.BooleanField(default=True)
    enable_sms = models.BooleanField(default=False)
    enable_whatsapp = models.BooleanField(default=False)
    
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cm_created_campaigns')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cm_updated_campaigns')
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cm_deleted_campaigns')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Campaign Manager Campaign"
        verbose_name_plural = "Campaign Manager Campaigns"

    def __str__(self):
        return self.name

# --- 3. SEQUENCE STEP MODEL ---
class SequenceStep(models.Model):
    class TriggerConditions(models.TextChoices):
        ALWAYS_SEND = 'always', 'Always Send'
        NO_RESPONSE = 'no_response', 'Send if no response'
        # --- NEW (from video 00:51) ---
        NO_ACTION = 'no_action', 'Send if no action taken'

    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.CASCADE, 
        related_name="cm_sequence_steps"
    )
    template = models.ForeignKey(Template, on_delete=models.PROTECT)
    channel = models.CharField(max_length=20, choices=Template.TEMPLATE_TYPES)
    
    step_order = models.PositiveIntegerField() 
    
    # --- UPDATED (from video 00:59) ---
    delay_minutes = models.PositiveIntegerField(default=0)
    delay_hours = models.PositiveIntegerField(default=0)
    delay_days = models.PositiveIntegerField(default=0)
    delay_weeks = models.PositiveIntegerField(default=0)
    
    trigger_condition = models.CharField(
        max_length=20, 
        choices=TriggerConditions.choices, 
        default=TriggerConditions.ALWAYS_SEND
    )
    
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cm_created_steps')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cm_updated_steps')
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cm_deleted_steps')

    class Meta:
        unique_together = ('campaign', 'step_order') 
        ordering = ['campaign', 'step_order']
        verbose_name = "Campaign Manager Step"
        verbose_name_plural = "Campaign Manager Steps"

    def __str__(self):
        return f"{self.campaign.name} - Step {self.step_order}"

# --- 4. CAMPAIGN LOG MODEL ---
class CampaignLog(models.Model):
    class LogStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        REPLIED = 'replied', 'Replied'
        OPENED = 'opened', 'Opened'
        CLICKED = 'clicked', 'Clicked'
        # --- NEW (from video) ---
        DELIVERED = 'delivered', 'Delivered' 

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="cm_logs")
    step = models.ForeignKey(SequenceStep, on_delete=models.CASCADE, related_name="cm_logs")
    contact = models.ForeignKey(AudienceContact, on_delete=models.CASCADE, related_name="cm_logs")
    
    status = models.CharField(max_length=20, choices=LogStatus.choices, default=LogStatus.PENDING)
    sent_at = models.DateTimeField(default=timezone.now)
    error_message = models.TextField(blank=True, null=True)
    response_received_at = models.DateTimeField(null=True, blank=True)
    
    # --- NEW (for webhook tracking) ---
    message_provider_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = "Campaign Manager Log"
        verbose_name_plural = "Campaign Manager Logs"

    def __str__(self):
        return f"Log: {self.campaign.name} to {self.contact.id} - {self.get_status_display()}"

# --- 5. NEW MODEL (to fix Pause/Resume bug) ---
class PendingTask(models.Model):
    """
    Stores Celery task IDs for campaigns that can be paused.
    """
    task_id = models.CharField(max_length=255, unique=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="cm_pending_tasks")
    contact = models.ForeignKey(AudienceContact, on_delete=models.CASCADE, related_name="cm_pending_tasks")
    step = models.ForeignKey(SequenceStep, on_delete=models.CASCADE, related_name="cm_pending_tasks")
    scheduled_for = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Task {self.task_id} for {self.campaign.name} - Step {self.step.step_order}"