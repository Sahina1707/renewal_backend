from rest_framework import serializers
from django.utils import timezone
from django.utils.functional import SimpleLazyObject
from datetime import timedelta
from .models import Campaign, CampaignType, CampaignRecipient, CampaignScheduleInterval
from apps.templates.models import Template
from apps.files_upload.models import FileUpload
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.renewals.models import RenewalCase
from apps.email_provider.models import EmailProviderConfig
from apps.target_audience.models import TargetAudience
from .models import CampaignScheduleInterval
from apps.templates.models import Template
from apps.email_provider.models import EmailProviderConfig
from django.utils import timezone

try:
    from apps.sms_provider.models import SmsProvider
except ImportError:
    SmsProvider = None

try:
    from apps.whatsapp_provider.models import WhatsAppProvider
except ImportError:
    WhatsAppProvider = None

class CampaignSerializer(serializers.ModelSerializer):
    simplified_status = serializers.SerializerMethodField()
    email_provider_name = serializers.SerializerMethodField()
    sms_provider_name = serializers.SerializerMethodField()
    whatsapp_provider_name = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'campaign_type', 'description', 'status', 'simplified_status',
            'target_count', 'upload', 'delivered_count', 'sent_count', 'opened_count',
            'clicked_count', 'total_responses', 'channels', 'target_audience',
            'email_provider', 'email_provider_name',
            'sms_provider' if hasattr(Campaign, 'sms_provider') else None,
            'sms_provider_name' if hasattr(Campaign, 'sms_provider') else None,
            'whatsapp_provider' if hasattr(Campaign, 'whatsapp_provider') else None,
            'whatsapp_provider_name' if hasattr(Campaign, 'whatsapp_provider') else None,
            'started_at', 'completed_at', 'is_recurring', 'recurrence_pattern',
            'subject_line', 'template', 'use_personalization', 'personalization_fields',
            'created_by', 'assigned_to', 'created_at', 'updated_at', 'delivery_rate',
            'open_rate', 'click_rate', 'response_rate',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'delivery_rate', 'open_rate', 'click_rate', 'response_rate', 'created_by']
        fields = [f for f in fields if f is not None]

    def get_simplified_status(self, obj):
        """Get simplified status for frontend"""
        return obj.get_simplified_status()

    def get_email_provider_name(self, obj):
        return obj.email_provider.name if obj.email_provider else "System Default"

    def get_sms_provider_name(self, obj):
        if hasattr(obj, 'sms_provider') and obj.sms_provider:
            return obj.sms_provider.name
        return "System Default"

    def get_whatsapp_provider_name(self, obj):
        if hasattr(obj, 'whatsapp_provider') and obj.whatsapp_provider:
            return obj.whatsapp_provider.name
        return "System Default"
class CampaignCreateSerializer(serializers.Serializer):
    file_upload_id = serializers.IntegerField(help_text="ID of the uploaded policy file from file_uploads table")
    campaign_name = serializers.CharField(max_length=200, required=False, help_text="Campaign name (defaults to file name if not provided)")
    campaign_type_id = serializers.IntegerField(help_text="ID of campaign type (should be email type)")
    template_id = serializers.IntegerField(help_text="ID of template to use for the campaign")
    email_provider_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of specific Email provider. Leave null for default."
    )
    sms_provider_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of specific SMS provider. Leave null for default."
    )

    whatsapp_provider_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of specific WhatsApp provider. Leave null for default."
    )
    TARGET_AUDIENCE_CHOICES = [
        ('pending_renewals', 'Pending Renewals'),
        ('expired_policies', 'Expired Policies'),
        ('all_customers', 'All Customers in File'),
    ]
    target_audience_id = serializers.IntegerField(
        required=False,
        help_text="ID of existing target audience (optional - not used in date-based logic)"
    )
    target_audience_type = serializers.ChoiceField(
        choices=TARGET_AUDIENCE_CHOICES,
        required=True,
        help_text="Type of target audience to filter (required for date-based logic)"
    )

    SCHEDULE_CHOICES = [
        ('immediate', 'Send Immediately'),
        ('scheduled', 'Schedule for Later'),
    ]
    schedule_type = serializers.ChoiceField(
        choices=SCHEDULE_CHOICES,
        default='immediate',
        help_text="When to send the campaign"
    )
    scheduled_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="When to send the campaign (required if schedule_type is 'scheduled')"
    )
    description = serializers.CharField(max_length=500, required=False, help_text="Campaign description")
    subject_line = serializers.CharField(max_length=200, required=False, help_text="Email subject line")
    send_immediately = serializers.BooleanField(required=False, default=False, help_text="Send emails immediately after creating campaign")
    enable_advanced_scheduling = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Enable multi-channel communication intervals"
    )
    schedule_intervals = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text="List of communication intervals for advanced scheduling"
    )

    def validate_file_upload_id(self, value):
        try:
            file_upload = FileUpload.objects.get(id=value)
            if file_upload.upload_status != 'completed':
                raise serializers.ValidationError("File upload must be completed before creating campaign")
            return value
        except FileUpload.DoesNotExist:
            raise serializers.ValidationError("File upload not found")

    def validate_campaign_type_id(self, value):
        try:
            campaign_type = CampaignType.objects.get(id=value)
            if 'email' not in campaign_type.default_channels:
                raise serializers.ValidationError("Campaign type must support email channel")
            return value
        except CampaignType.DoesNotExist:
            raise serializers.ValidationError("Campaign type not found")

    def validate_template_id(self, value):
        try:
            template = Template.objects.get(id=value)
            if template.channel is not None and template.channel != 'email':
                raise serializers.ValidationError(f"Template must be an email template. Found channel: {template.channel}")
            if not template.is_active:
                raise serializers.ValidationError("Template must be active")
            return value
        except Template.DoesNotExist:
            raise serializers.ValidationError("Template not found")

    def validate_target_audience_id(self, value):
        if value is None:
            return value
        try:
            from apps.target_audience.models import TargetAudience
            TargetAudience.objects.get(id=value)
            return value
        except TargetAudience.DoesNotExist:
            raise serializers.ValidationError("Target audience not found")

    def validate_email_provider_id(self, value):
        if value is None:
            return value
        try:
            provider = EmailProviderConfig.objects.get(id=value, is_deleted=False)
            if not provider.is_active:
                raise serializers.ValidationError("Selected Email provider is not active")
            return value
        except EmailProviderConfig.DoesNotExist:
            raise serializers.ValidationError("Email provider not found")

    def validate_sms_provider_id(self, value):
        if not value:
            return value
        try:
            provider = SmsProvider.objects.get(id=value, is_deleted=False)
            if not provider.is_active:
                raise serializers.ValidationError("Selected SMS provider is not active")
            return value
        except (ImportError, SmsProvider.DoesNotExist):
            raise serializers.ValidationError("SMS provider not found or app not installed")

    def validate_whatsapp_provider_id(self, value):
        if not value: return None
        try:
            provider = WhatsAppProvider.objects.get(id=value, is_deleted=False)
            if not provider.is_active:
                raise serializers.ValidationError("Selected WhatsApp provider is not active")
            return value
        except (ImportError, WhatsAppProvider.DoesNotExist):
            raise serializers.ValidationError("WhatsApp provider not found or app not installed")

    def validate(self, data):
        schedule_type = data.get('schedule_type', 'immediate')
        scheduled_at = data.get('scheduled_at')
        
        if schedule_type == 'scheduled':
            if not scheduled_at:
                raise serializers.ValidationError({
                    'scheduled_at': 'Scheduled time is required when schedule_type is "scheduled"'
                })
            
            from django.utils import timezone
            if scheduled_at <= timezone.now():
                raise serializers.ValidationError({
                    'scheduled_at': 'Scheduled time must be in the future'
                })
        
        return data

    def validate_schedule_intervals(self, value):
        if not value:
            return value
        
        valid_channels = ['email', 'whatsapp', 'sms', 'phone', 'push']
        valid_units = ['minutes', 'hours', 'days', 'weeks']
        valid_conditions = ['no_response', 'no_action', 'no_engagement', 'always']
        
        for i, interval in enumerate(value):
            if 'channel' not in interval:
                raise serializers.ValidationError(f"Interval {i+1}: 'channel' is required")
            if 'delay_value' not in interval:
                raise serializers.ValidationError(f"Interval {i+1}: 'delay_value' is required")
            if 'delay_unit' not in interval:
                raise serializers.ValidationError(f"Interval {i+1}: 'delay_unit' is required")
            
            if interval['channel'] not in valid_channels:
                raise serializers.ValidationError(f"Interval {i+1}: Invalid channel '{interval['channel']}'. Must be one of {valid_channels}")
            
            if interval['delay_unit'] not in valid_units:
                raise serializers.ValidationError(f"Interval {i+1}: Invalid delay_unit '{interval['delay_unit']}'. Must be one of {valid_units}")
            
            try:
                delay_value = int(interval['delay_value'])
                if delay_value <= 0:
                    raise serializers.ValidationError(f"Interval {i+1}: delay_value must be greater than 0")
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Interval {i+1}: delay_value must be a positive integer")
            
            if 'trigger_conditions' in interval:
                for condition in interval['trigger_conditions']:
                    if condition not in valid_conditions:
                        raise serializers.ValidationError(f"Interval {i+1}: Invalid trigger condition '{condition}'. Must be one of {valid_conditions}")
        return value

    def create(self, validated_data):
        file_upload = FileUpload.objects.get(id=validated_data['file_upload_id'])
        campaign_type = CampaignType.objects.get(id=validated_data['campaign_type_id'])
        template = Template.objects.get(id=validated_data['template_id'])

        campaign_name = validated_data.get('campaign_name', file_upload.original_filename)

        target_audience = None
        if validated_data.get('target_audience_type'):
            try:
                target_audience = self._get_or_create_target_audience(validated_data['target_audience_type'], file_upload)
            except Exception as e:
                print(f"Warning: Could not create target audience due to permissions: {e}")
                target_audience = None
        elif validated_data.get('target_audience_id'):
            from apps.target_audience.models import TargetAudience
            target_audience = TargetAudience.objects.get(id=validated_data['target_audience_id'])

        email_provider = None
        if validated_data.get('email_provider_id'):
            email_provider = EmailProviderConfig.objects.get(id=validated_data['email_provider_id'])

        sms_provider = None
        if validated_data.get('sms_provider_id'):
            try:
                sms_provider = SmsProvider.objects.get(id=validated_data['sms_provider_id'])
            except (ImportError, SmsProvider.DoesNotExist):
                pass 

        whatsapp_provider = None
        if validated_data.get('whatsapp_provider_id'):
            try:
                whatsapp_provider = WhatsAppProvider.objects.get(id=validated_data['whatsapp_provider_id'])
            except (ImportError, WhatsAppProvider.DoesNotExist): pass

        schedule_type = validated_data.get('schedule_type', 'immediate')
        scheduled_at = validated_data.get('scheduled_at')
        
        if schedule_type == 'scheduled' and scheduled_at:
            campaign_status = 'scheduled'
            started_at = scheduled_at
        else:
            campaign_status = 'draft'
            started_at = timezone.now()

        campaign_data = {
            'name': campaign_name,
            'campaign_type': campaign_type,
            'template': template,
            'description': validated_data.get('description', f"Campaign created from file: {file_upload.original_filename}"),
            'status': campaign_status,
            'upload': file_upload,
            'target_audience': target_audience,
            'email_provider': email_provider,
            'sms_provider': sms_provider,
            'whatsapp_provider': whatsapp_provider,
            'channels': ['email'],
            'schedule_type': schedule_type,
            'scheduled_at': scheduled_at,
            'started_at': started_at,
            'subject_line': validated_data.get('subject_line', template.subject),
            'enable_advanced_scheduling': validated_data.get('enable_advanced_scheduling', False),
            'advanced_scheduling_config': validated_data.get('schedule_intervals', []),
            'created_by': self.context['request'].user if 'request' in self.context else SimpleLazyObject(lambda: get_user_model().objects.first()),
            'assigned_to': self._get_assigned_agent()
        }

        if not hasattr(Campaign, 'sms_provider'):
            campaign_data.pop('sms_provider', None)
        if not hasattr(Campaign, 'whatsapp_provider'):
            campaign_data.pop('whatsapp_provider', None)

        campaign = Campaign.objects.create(**campaign_data)

        if validated_data.get('enable_advanced_scheduling') and validated_data.get('schedule_intervals'):
            self._create_schedule_intervals(campaign, validated_data['schedule_intervals'])

        target_audience_type_for_recipients = validated_data.get('target_audience_type', 'all_customers')
        if validated_data.get('target_audience_id') and target_audience:
            target_audience_type_for_recipients = 'all_customers'

        target_count = self._create_campaign_recipients(campaign, target_audience_type_for_recipients, file_upload)

        campaign.target_count = target_count
        campaign.save()

        if schedule_type == 'immediate' and validated_data.get('send_immediately', False):
            try:
                from .services import EmailCampaignService
                import logging

                logger = logging.getLogger(__name__)
                logger.info(f"Starting immediate email sending for campaign {campaign.pk}")

                result = EmailCampaignService.send_campaign_emails(campaign.pk)

                if "error" in result:
                    logger.error(f"Email sending failed: {result['error']}")
                    campaign.status = 'draft'
                    campaign.description += f" [Email Error: {result['error']}]"
                elif "message" in result and "No pending recipients found" in str(result.get("message", "")):
                    logger.warning(f"No recipients found: {result['message']}")
                    campaign.status = 'draft'
                    campaign.description += f" [Warning: {result['message']}]"
                elif "success" in result:
                    sent_count = int(result.get('sent_count', 0))
                    failed_count = int(result.get('failed_count', 0))

                    logger.info(f"Email sending completed: {sent_count} sent, {failed_count} failed")

                    if sent_count > 0:
                        campaign.status = 'completed'
                        campaign.description += f" [Success: {sent_count} emails sent]"
                    else:
                        campaign.status = 'draft'
                        campaign.description += f" [Warning: No emails sent, {failed_count} failed]"
                else:
                    logger.info(f"Email sending result: {result}")
                    campaign.status = 'completed'

            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Exception during email sending: {str(e)}")
                campaign.status = 'draft'
                campaign.description += f" [Exception: {str(e)}]"

            campaign.save()
            
        elif schedule_type == 'scheduled' and scheduled_at:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Campaign {campaign.pk} saved as scheduled for {scheduled_at}. Background task scheduling is currently disabled.")
            campaign.description += f" [Scheduled for {scheduled_at} (Task not queued)]"
            campaign.save()

        return campaign

    def _get_or_create_target_audience(self, target_audience_type, file_upload):

        audience_name_map = {
            'pending_renewals': f"Pending Renewals - {file_upload.original_filename}",
            'expired_policies': f"Expired Policies - {file_upload.original_filename}",
            'all_customers': f"All Customers - {file_upload.original_filename}"
        }

        audience_name = audience_name_map.get(target_audience_type, f"Custom Audience - {file_upload.original_filename}")
        unique_key = f"{target_audience_type}_{file_upload.id}_{file_upload.created_at.strftime('%Y%m%d')}"

        try:
            target_audience = TargetAudience.objects.get(key=unique_key)
            return target_audience
        except TargetAudience.DoesNotExist:
            pass

        try:
            target_audience = TargetAudience.objects.create(
                key=unique_key,
                name=audience_name,
                description=f"Auto-created audience for {target_audience_type} from file {file_upload.original_filename}"
            )
            return target_audience
        except Exception as e:
            target_audience, created = TargetAudience.objects.get_or_create(
                name=audience_name,
                defaults={
                    'key': f"fallback_{target_audience_type}_{file_upload.id}",
                    'description': f"Fallback audience for {target_audience_type} from file {file_upload.original_filename}"
                }
            )
            return target_audience

    def _get_assigned_agent(self):
        from django.contrib.auth import get_user_model
        from django.db.models import Count

        User = get_user_model()

        available_agents = User.objects.filter(
            is_staff=True,
            is_active=True
        ).annotate(
            campaign_count=Count('assigned_campaigns')
        ).order_by('campaign_count')

        return available_agents.first() if available_agents.exists() else None

    def _create_campaign_recipients(self, campaign, target_audience_type, file_upload):
        from django.db import transaction
        import logging

        logger = logging.getLogger(__name__)
        recipients_created = 0

        existing_recipients = CampaignRecipient.objects.filter(campaign=campaign).count()
        if existing_recipients > 0:
            logger.warning(f"Campaign {campaign.id} already has {existing_recipients} recipients. Skipping recipient creation.")
            return existing_recipients

        with transaction.atomic():
            recipients_to_create = []

            if target_audience_type == 'pending_renewals':
                from datetime import date
                today = date.today()
                
                policies = Policy.objects.filter(
                    status='active',                   
                    renewal_date__lte=today,           
                    end_date__gt=today,              
                    customer__email__isnull=False,   
                    customer__email__gt=''
                ).select_related('customer')

                if file_upload:
                    upload_time = file_upload.created_at
                    time_window_start = upload_time - timedelta(hours=1)
                    time_window_end = upload_time + timedelta(hours=1)

                    file_related_policies = policies.filter(
                        created_at__range=(time_window_start, time_window_end)
                    )

                    if file_related_policies.exists():
                        policies = file_related_policies
                    else:
                        policies = policies.order_by('-created_at')[:file_upload.successful_records]

                for policy in policies:
                    recipients_to_create.append(
                        CampaignRecipient(
                            campaign=campaign,
                            customer=policy.customer,
                            policy=policy,
                            email_status='pending',
                            whatsapp_status='pending',
                            sms_status='pending'
                        )
                    )

            elif target_audience_type == 'expired_policies':
                from datetime import date
                today = date.today()
                
                expired_policies = Policy.objects.filter(
                    status='active',                   
                    end_date__lt=today,               
                    customer__email__isnull=False,    
                    customer__email__gt=''
                ).select_related('customer')

                if file_upload:
                    upload_time = file_upload.created_at
                    time_window_start = upload_time - timedelta(hours=1)
                    time_window_end = upload_time + timedelta(hours=1)

                    file_related_policies = expired_policies.filter(
                        created_at__range=(time_window_start, time_window_end)
                    )

                    if file_related_policies.exists():
                        expired_policies = file_related_policies
                    else:
                        expired_policies = expired_policies.order_by('-created_at')[:file_upload.successful_records]

                for policy in expired_policies:
                    recipients_to_create.append(
                        CampaignRecipient(
                            campaign=campaign,
                            customer=policy.customer,
                            policy=policy,
                            email_status='pending',
                            whatsapp_status='pending',
                            sms_status='pending'
                        )
                    )

            elif target_audience_type == 'all_customers':
                customers = Customer.objects.filter(
                    is_deleted=False,
                    email__isnull=False,
                    email__gt=''
                )

                if file_upload:
                    target_count = file_upload.successful_records if file_upload.successful_records > 0 else customers.count()
                    
                    upload_time = file_upload.created_at
                    time_window_start = upload_time - timedelta(hours=2)
                    time_window_end = upload_time + timedelta(hours=2)

                    file_related_customers = customers.filter(
                        created_at__range=(time_window_start, time_window_end)
                    )

                    if file_related_customers.exists():
                        customers = file_related_customers.order_by('-created_at')[:target_count]
                    else:
                        customers = customers.order_by('-created_at')[:target_count]
                else:
                    logger.info(f"No file upload specified, using all customers")

                customer_ids = list(customers.values_list('id', flat=True))

                latest_policies = {}
                if customer_ids:
                    all_policies = Policy.objects.filter(
                        customer__in=customer_ids
                    ).select_related('customer').order_by('customer', '-created_at')

                    seen_customers = set()
                    for policy in all_policies:
                        if policy.customer.pk not in seen_customers:
                            latest_policies[policy.customer.pk] = policy
                            seen_customers.add(policy.customer.pk)

                for customer in customers:
                    latest_policy = latest_policies.get(customer.pk)

                    recipients_to_create.append(
                        CampaignRecipient(
                            campaign=campaign,
                            customer=customer,
                            policy=latest_policy,
                            email_status='pending',
                            whatsapp_status='pending',
                            sms_status='pending'
                        )
                    )

            if recipients_to_create:
                try:
                    recipients_to_create.sort(
                        key=lambda r: (
                            getattr(r.customer, 'id', 0) or 0,
                            (getattr(getattr(r, 'policy', None), 'id', 0) or 0)
                        )
                    )
                except Exception:
                    pass

                existing_customer_ids = set(
                    CampaignRecipient.objects.filter(campaign=campaign).values_list('customer_id', flat=True)
                )

                for recipient_data in recipients_to_create:
                    if recipient_data.customer.id in existing_customer_ids:
                        continue

                    try:
                        import uuid
                        import hashlib
                        unique_string = f"{campaign.id}-{recipient_data.customer.id}-{uuid.uuid4()}"
                        tracking_id = hashlib.sha256(unique_string.encode()).hexdigest()[:32]

                        recipient = CampaignRecipient.objects.create(
                            campaign=recipient_data.campaign,
                            customer=recipient_data.customer,
                            policy=recipient_data.policy,
                            email_status=recipient_data.email_status,
                            whatsapp_status=recipient_data.whatsapp_status,
                            sms_status=recipient_data.sms_status, 
                            tracking_id=tracking_id,
                            created_by=self.context['request'].user
                        )
                        recipients_created += 1

                        self._add_email_tracking(recipient)

                    except Exception as e:
                        logger.warning(f"Failed to create recipient for customer {recipient_data.customer.id}: {str(e)}")
                        continue

        return recipients_created

    def _add_email_tracking(self, recipient):
        """Add tracking pixel and convert links for email tracking"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            tracking_pixel_url = f"{base_url}/api/campaigns/track-open/?t={recipient.tracking_id}"
            tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" alt="" />'

        except Exception as e:
            logger.warning(f"Failed to add email tracking for recipient {recipient.id}: {str(e)}")

    def _create_schedule_intervals(self, campaign, schedule_intervals):
        """Create CampaignScheduleInterval objects for advanced scheduling intervals"""
       
        created_intervals = []
        
        for i, interval_data in enumerate(schedule_intervals, 1):
            if interval_data.get('template_id'):
                try:
                    template = Template.objects.get(id=interval_data['template_id'])
                except Template.DoesNotExist:
                    pass  
            
            base_time = campaign.scheduled_at or campaign.started_at or timezone.now()
            scheduled_time = self._calculate_interval_time(
                base_time, 
                interval_data['delay_value'], 
                interval_data['delay_unit']
            )
            
            schedule_interval = CampaignScheduleInterval.objects.create(
                campaign=campaign,
                template=template,
                sequence_order=i,
                channel=interval_data['channel'],
                delay_value=interval_data['delay_value'],
                delay_unit=interval_data['delay_unit'],
                trigger_conditions=interval_data.get('trigger_conditions', ['always']),
                is_active=interval_data.get('is_active', True),
                scheduled_at=scheduled_time,
                created_by=self.context['request'].user if 'request' in self.context else SimpleLazyObject(lambda: get_user_model().objects.first())
            )
            
            created_intervals.append(schedule_interval)
        
        return created_intervals
    
    def _calculate_interval_time(self, base_time, delay_value, delay_unit):
        """Calculate the scheduled time for an interval"""
        if delay_unit == 'minutes':
            return base_time + timedelta(minutes=delay_value)
        elif delay_unit == 'hours':
            return base_time + timedelta(hours=delay_value)
        elif delay_unit == 'days':
            return base_time + timedelta(days=delay_value)
        elif delay_unit == 'weeks':
            return base_time + timedelta(weeks=delay_value)
        else:
            return base_time
class CampaignScheduleIntervalSerializer(serializers.ModelSerializer):
    """Serializer for CampaignScheduleInterval model"""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    delay_description = serializers.CharField(source='get_delay_description', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)    
    class Meta:
        model = CampaignScheduleInterval
        fields = [ 
            'id', 'campaign', 'campaign_name', 'template', 'template_name',
            'sequence_order',
            'channel', 'channel_display', 'delay_value', 'delay_unit',
            'delay_description', 'trigger_conditions', 'is_active', 'is_sent',
            'scheduled_at', 'sent_at', 'created_by', 'created_by_name', 
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'campaign_name', 'template_name', 
            'channel_display', 'delay_description', 'created_by_name',
            'is_sent', 'sent_at', 'created_at', 'updated_at'
        ]
class CampaignScheduleIntervalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CampaignScheduleInterval"""
    class Meta:
        model = CampaignScheduleInterval
        fields = [
            'campaign', 'template', 'sequence_order', 
            'channel', 'delay_value', 'delay_unit', 'trigger_conditions',
            'is_active', 'scheduled_at'
        ]
    
    def validate_campaign(self, value):
        if value.is_deleted:
            raise serializers.ValidationError("Cannot create interval for deleted campaign")
        return value
    
    def validate_template(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot use inactive template")
        return value
    
    def validate_sequence_order(self, value):
        campaign = self.initial_data.get('campaign')
        if campaign and value:
            existing = CampaignScheduleInterval.objects.filter(
                campaign=campaign,
                sequence_order=value,
                is_deleted=False
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    f"Sequence order {value} already exists for this campaign"
                )
        return value
    
    def validate_trigger_conditions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Trigger conditions must be a list")
        
        valid_conditions = [choice[0] for choice in CampaignScheduleInterval.TRIGGER_CONDITION_CHOICES]
        for condition in value:
            if condition not in valid_conditions:
                raise serializers.ValidationError(
                    f"Invalid trigger condition: {condition}. Must be one of {valid_conditions}"
                )
        return value
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user if 'request' in self.context else SimpleLazyObject(lambda: get_user_model().objects.first())
        return super().create(validated_data)

class CampaignScheduleIntervalUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CampaignScheduleInterval"""
    class Meta:
        model = CampaignScheduleInterval
        fields = [
            'template', 'sequence_order', 
            'channel', 'delay_value', 'delay_unit', 'trigger_conditions',
            'is_active', 'scheduled_at'
        ]
    
    def validate_template(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot use inactive template")
        return value
    
    def validate_sequence_order(self, value):
        if self.instance and value:
            existing = CampaignScheduleInterval.objects.filter(
                campaign=self.instance.campaign,
                sequence_order=value,
                is_deleted=False
            ).exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError(
                    f"Sequence order {value} already exists for this campaign"
                )
        return value
    
    def validate_trigger_conditions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Trigger conditions must be a list")
        
        valid_conditions = [choice[0] for choice in CampaignScheduleInterval.TRIGGER_CONDITION_CHOICES]
        for condition in value:
            if condition not in valid_conditions:
                raise serializers.ValidationError(
                    f"Invalid trigger condition: {condition}. Must be one of {valid_conditions}"
                )
        return value
    
    def update(self, instance, validated_data):
        validated_data['updated_by'] = self.context['request'].user if 'request' in self.context else SimpleLazyObject(lambda: get_user_model().objects.first())
        return super().update(instance, validated_data)