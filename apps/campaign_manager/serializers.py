from rest_framework import serializers
from .models import Campaign, SequenceStep, CampaignLog, PendingTask
from apps.audience_manager.models import Audience, AudienceContact
from apps.templates.models import Template
from django.utils import timezone
from apps.whatsapp_provider.services import WhatsAppService, WhatsAppAPIError
from apps.whatsapp_provider.models import WhatsAppMessageTemplate, WhatsAppProvider
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
        Create a campaign and launch it immediately (Synchronously) if active.
        """
        steps_data = validated_data.pop('cm_sequence_steps')
        
        scheduled_date = validated_data.get('scheduled_date')
        
        if scheduled_date and scheduled_date > timezone.now():
            # This is a scheduled campaign. We will NOT send it yet.
            validated_data['status'] = Campaign.CampaignStatus.SCHEDULED
            campaign = Campaign.objects.create(**validated_data)
            for step_data in steps_data:
                SequenceStep.objects.create(campaign=campaign, **step_data)
            return campaign
        
        else:
            # This is an immediate-send campaign.
            validated_data['status'] = Campaign.CampaignStatus.ACTIVE
            campaign = Campaign.objects.create(**validated_data)
            for step_data in steps_data:
                SequenceStep.objects.create(campaign=campaign, **step_data)
        
        
        # --- RUN THE CAMPAIGN *NOW* ---
        print(f"--- SYNCHRONOUS: Processing campaign_id: {campaign.id} ---")
        
        contacts = campaign.audience.contacts.filter(is_deleted=False)
        first_step = campaign.cm_sequence_steps.filter(step_order=1).first()

        if not contacts.exists():
            print("--- SYNCHRONOUS: Campaign has no contacts. ---")
            campaign.status = Campaign.CampaignStatus.COMPLETED
            campaign.save()
            return campaign

        if not first_step:
            print("--- SYNCHRONOUS: Campaign has no steps. ---")
            campaign.status = Campaign.CampaignStatus.COMPLETED
            campaign.save()
            return campaign

        print(f"--- SYNCHRONOUS: Found {contacts.count()} contacts. Sending... ---")
        
        # --- PREPARE WHATSAPP SERVICE ---
        service = None
        provider_template = None

        if first_step.channel == 'whatsapp' and campaign.enable_whatsapp:
            campaign_template = first_step.template # Old template object
            try:
                # Get default provider
                service = WhatsAppService().get_service_instance()
                
                # Find matching provider template
                provider_template = WhatsAppMessageTemplate.objects.get(
                    name=campaign_template.name,
                    provider=service.provider,
                    status='approved'
                )
            except WhatsAppProvider.DoesNotExist as e:
                print(f"--- SYNCHRONOUS: FAILED. No default WhatsApp provider. {e} ---")
                # We continue, but individual sends will fail below
            except WhatsAppMessageTemplate.DoesNotExist:
                print(f"--- SYNCHRONOUS: FAILED. No matching template found. ---")
                # We continue, individual sends will fail

        # --- LOOP THROUGH CONTACTS ---
        for contact in contacts:
            success = False
            error_msg = None
            message_id = None
            
            if first_step.channel == 'whatsapp' and campaign.enable_whatsapp:
                if contact.phone and service and provider_template:
                    try:
                        # --- FIXED LOGIC: DELEGATE PARAMETERS TO SERVICE ---
                        # We send an empty list [] so the Service triggers its auto-mapper.
                        # We MUST pass 'customer=contact' so the Service has data to map.
                        
                        print(f"--- SYNCHRONOUS: Sending WhatsApp to {contact.phone} via {service.provider.name}... ---")
                        
                        response = service.send_template_message(
                            to_phone=contact.phone,
                            template=provider_template, 
                            template_params=[], # <--- EMPTY LIST triggers the fix in services.py
                            campaign=campaign,
                            customer=contact    # <--- CRITICAL: Service uses this to fill "Valued Customer"
                        )
                        
                        success = True
                        message_id = response['messages'][0]['id']
                    
                    except WhatsAppAPIError as e:
                        print(f"--- SYNCHRONOUS: API Error for {contact.phone}: {e}")
                        success = False
                        error_msg = str(e)
                    except Exception as e:
                        print(f"--- SYNCHRONOUS: General Error for {contact.phone}: {e}")
                        success = False
                        error_msg = f"General send error: {e}"

                elif not contact.phone:
                    print(f"--- SYNCHRONOUS: Skipping {contact.id}, no phone. ---")
                    error_msg = "Contact has no phone number."
                else:
                    error_msg = "Service or Template not initialized."

            # --- 2. NEW SMS LOGIC (With Variable Replacement) ---
            elif first_step.channel == 'sms' and campaign.enable_sms:
                if contact.phone:
                    try:
                        print(f"--- SYNCHRONOUS: Sending SMS to {contact.phone}... ---")
                        
                        # 1. Get Service (Default)
                        sms_service = SmsService().get_service_instance()
                        
                        # 2. Prepare Message Body
                        # The template body is: "Hi {{1}}, your policy {{2}} expires on {{3}}"
                        # We need to map variables like ['name', 'policy_number', 'expiry_date'] to {{1}}, {{2}}, {{3}}
                        
                        message_body = first_step.template.content
                        variable_list = first_step.template.variables # e.g. ['name', 'policy_number']
                        
                        if variable_list:
                            # Loop through the variables (index 1, 2, 3...)
                            for index, var_name in enumerate(variable_list, start=1):
                                # Get data from contact (e.g., contact.name)
                                val = getattr(contact, var_name, None)
                                
                                # Fallback if empty
                                if not val:
                                    val = "Customer" if var_name == 'name' else "Pending"
                                
                                # Replace {{1}} with the value
                                placeholder = f"{{{{{index}}}}}" # Creates "{{1}}", "{{2}}"
                                message_body = message_body.replace(placeholder, str(val))
                                
                                # Also try replacing named variables {{name}} just in case
                                message_body = message_body.replace(f"{{{{{var_name}}}}}", str(val))
                        
                        # 3. Send
                        result = sms_service.send_sms(contact.phone, message_body, campaign=campaign, contact=contact)
                        
                        success = True
                        message_id = result.get('sid')

                    except (SmsApiException, Exception) as e:
                        print(f"--- SYNCHRONOUS: SMS Error for {contact.phone}: {e}")
                        success = False
                        error_msg = str(e)
                else:
                    error_msg = "Contact has no phone number."
            # --- LOG THE RESULT ---
            CampaignLog.objects.create(
                campaign=campaign,
                step=first_step,
                contact=contact,
                status=CampaignLog.LogStatus.SENT if success else CampaignLog.LogStatus.FAILED,
                sent_at=timezone.now(),
                error_message=error_msg,
                message_provider_id=message_id
            )
        
        print(f"--- SYNCHRONOUS: Sending complete. ---")
        campaign.status = Campaign.CampaignStatus.COMPLETED
        campaign.save()
        
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