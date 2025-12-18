from rest_framework import serializers
from .models import Campaign, SequenceStep, CampaignLog, PendingTask
from apps.audience_manager.models import Audience, AudienceContact
from apps.templates.models import Template
from django.utils import timezone
from apps.whatsapp_provider.services import WhatsAppService, WhatsAppAPIError
from apps.whatsapp_provider.models import WhatsAppMessageTemplate, WhatsAppProvider
from apps.email_provider.services import EmailProviderService
from apps.email_provider.models import EmailProviderConfig
from apps.sms_provider.services import SmsService, SmsApiException
import logging

logger = logging.getLogger(__name__)


class SequenceStepSerializer(serializers.ModelSerializer):
    template = serializers.PrimaryKeyRelatedField(queryset=Template.objects.all())
    class Meta:
        model = SequenceStep
        fields = [
            'id', 'template', 'channel', 'step_order', 'delay_minutes',
            'delay_hours', 'delay_days', 'delay_weeks', 'trigger_condition'
        ]

class CampaignSerializer(serializers.ModelSerializer):
    sequence_steps = SequenceStepSerializer(many=True, source='cm_sequence_steps')
    audience = serializers.PrimaryKeyRelatedField(queryset=Audience.objects.all())
    audience_name = serializers.StringRelatedField(source='audience', read_only=True)
    
    total_contacts = serializers.SerializerMethodField()
    log_counts = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'description', 'campaign_type', 'status', 
            'audience', 'audience_name', 'scheduled_date', 'enable_email',
            'enable_sms', 'enable_whatsapp', 'created_at', 'sequence_steps',
            'total_contacts', 'log_counts',
        ]
        read_only_fields = ['created_at', 'status', 'audience_name', 'total_contacts', 'log_counts']

    def get_total_contacts(self, obj):
        if obj.audience:
            return obj.audience.contacts.count()
        return 0

    def get_log_counts(self, obj):
        logs = obj.cm_logs
        return {
            "total": logs.count(),
            "sent": logs.filter(status=CampaignLog.LogStatus.SENT).count(),
            "delivered": logs.filter(status=CampaignLog.LogStatus.DELIVERED).count(),
            "failed": logs.filter(status=CampaignLog.LogStatus.FAILED).count(),
            "replied": logs.filter(status=CampaignLog.LogStatus.REPLIED).count(),
            "opened": logs.filter(status=CampaignLog.LogStatus.OPENED).count(),
            "clicked": logs.filter(status=CampaignLog.LogStatus.CLICKED).count(),
        }
    def create(self, validated_data):
        """
        Only save the data. Do NOT send emails here. 
        The View will handle the sending via Celery.
        """
        # Extract the steps data
        steps_data = validated_data.pop('cm_sequence_steps')
        
        # 1. Check if this is scheduled for the future
        scheduled_date = validated_data.get('scheduled_date')
        if scheduled_date and scheduled_date > timezone.now():
            validated_data['status'] = Campaign.CampaignStatus.SCHEDULED
        else:
            # Initially set to DRAFT. 
            # The View will change this to ACTIVE and start the background task.
            validated_data['status'] = Campaign.CampaignStatus.DRAFT 
            
        # 2. Save the Campaign to the Database
        campaign = Campaign.objects.create(**validated_data)
        
        # 3. Save the Steps to the Database
        for step_data in steps_data:
            SequenceStep.objects.create(campaign=campaign, **step_data)
            
        return campaign    
    
    def update(self, instance, validated_data):
        """
        Update an existing campaign.
        """
        steps_data = validated_data.pop('cm_sequence_steps', None)

        if instance.status == Campaign.CampaignStatus.ACTIVE and steps_data is not None:
            raise serializers.ValidationError(
                "Cannot edit steps on an active campaign. Please pause the campaign first."
            )

        # Update standard fields
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.campaign_type = validated_data.get('campaign_type', instance.campaign_type)
        instance.audience = validated_data.get('audience', instance.audience)
        instance.scheduled_date = validated_data.get('scheduled_date', instance.scheduled_date)
        
        instance.enable_email = validated_data.get('enable_email', instance.enable_email)
        instance.enable_sms = validated_data.get('enable_sms', instance.enable_sms)
        instance.enable_whatsapp = validated_data.get('enable_whatsapp', instance.enable_whatsapp)
        
        if instance.scheduled_date and instance.scheduled_date > timezone.now():
             instance.status = Campaign.CampaignStatus.SCHEDULED
        
        instance.save()
        if steps_data is not None:
            instance.cm_sequence_steps.all().delete() 
            for step_data in steps_data:
                SequenceStep.objects.create(campaign=instance, **step_data)
                
        return instance 

class CampaignLogSerializer(serializers.ModelSerializer):
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
            'step_order',
            'message_provider_id'
        ]