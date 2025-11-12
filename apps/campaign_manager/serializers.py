# File: apps/campaign_manager/serializers.py
#
# --- THIS IS THE CORRECTED VERSION ---

from rest_framework import serializers
from .models import Campaign, SequenceStep, CampaignLog

# --- Import your other models ---
from apps.audience_manager.models import Audience
from apps.templates.models import Template


class SequenceStepSerializer(serializers.ModelSerializer):
    """
    Handles the nested sequence steps for creating/updating a campaign.
    """
    template = serializers.PrimaryKeyRelatedField(queryset=Template.objects.all())

    class Meta:
        model = SequenceStep
        fields = [
            'id', 
            'template', 
            'channel', 
            'step_order', 
            'delay_days', 
            'delay_hours', 
            'trigger_condition'
        ]

class CampaignSerializer(serializers.ModelSerializer):
    """
    This is the main serializer. It handles the full
    CRUD for campaigns, including the nested steps.
    """
    
    # --- THIS IS THE FIX ---
    # We must tell the serializer that the "source" of this field
    # is the attribute we named 'cm_sequence_steps' in models.py
    sequence_steps = SequenceStepSerializer(many=True, source='cm_sequence_steps')
    # --- END OF FIX ---

    # --- READ/WRITE FIELDS FOR DROPDOWNS ---
    audience = serializers.PrimaryKeyRelatedField(queryset=Audience.objects.all())
    audience_name = serializers.StringRelatedField(source='audience', read_only=True)
    
    # --- KEY METRICS ---
    log_counts = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'id', 
            'name', 
            'campaign_type', 
            'status', 
            'audience', 
            'audience_name',
            'scheduled_date', 
            'created_at',
            'sequence_steps',
            'log_counts',
        ]
        read_only_fields = ['created_at', 'status', 'audience_name', 'log_counts']

    def get_log_counts(self, obj):
        # The related_name here must also match
        return {
            "sent": obj.cm_logs.filter(status=CampaignLog.LogStatus.SENT).count(),
            "failed": obj.cm_logs.filter(status=CampaignLog.LogStatus.FAILED).count(),
            "replied": obj.cm_logs.filter(status=CampaignLog.LogStatus.REPLIED).count(),
            "opened": obj.cm_logs.filter(status=CampaignLog.LogStatus.OPENED).count(),
            "clicked": obj.cm_logs.filter(status=CampaignLog.LogStatus.CLICKED).count(),
        }

    def create(self, validated_data):
        # We use the 'source' name here
        steps_data = validated_data.pop('cm_sequence_steps')
        campaign = Campaign.objects.create(**validated_data)
        for step_data in steps_data:
            SequenceStep.objects.create(campaign=campaign, **step_data)
        return campaign

    def update(self, instance, validated_data):
        # We use the 'source' name here
        steps_data = validated_data.pop('cm_sequence_steps', None)

        # Update simple fields
        instance.name = validated_data.get('name', instance.name)
        instance.campaign_type = validated_data.get('campaign_type', instance.campaign_type)
        instance.audience = validated_data.get('audience', instance.audience)
        instance.scheduled_date = validated_data.get('scheduled_date', instance.scheduled_date)
        instance.save()

        # Update nested steps
        if steps_data is not None:
            # We access the steps via the related_name
            instance.cm_sequence_steps.all().delete() # Delete old
            for step_data in steps_data: # Create new
                SequenceStep.objects.create(campaign=instance, **step_data)
                
        return instance

class CampaignLogSerializer(serializers.ModelSerializer):
    """
    A read-only serializer for viewing logs.
    """
    contact_email = serializers.StringRelatedField(source='contact.email', read_only=True)
    step_order = serializers.StringRelatedField(source='step.step_order', read_only=True)

    class Meta:
        model = CampaignLog
        fields = [
            'id', 
            'status', 
            'sent_at', 
            'error_message', 
            'contact_email', 
            'step_order'
        ]