from django.contrib import admin
from .models import Campaign, SequenceStep, CampaignLog, PendingTask

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'campaign_type', 'audience', 'scheduled_date', 'created_at')
    list_filter = ('status', 'campaign_type')
    search_fields = ('name', 'audience__name')

@admin.register(SequenceStep)
class SequenceStepAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'step_order', 'channel', 'delay_days', 'delay_hours', 'trigger_condition')
    list_filter = ('channel', 'trigger_condition')
    search_fields = ('campaign__name',)

@admin.register(CampaignLog)
class CampaignLogAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'step', 'contact', 'status', 'sent_at', 'message_provider_id')
    list_filter = ('status',)
    search_fields = ('campaign__name', 'contact__email', 'message_provider_id')

@admin.register(PendingTask)
class PendingTaskAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'campaign', 'contact', 'step', 'scheduled_for')
    search_fields = ('task_id', 'campaign__name')