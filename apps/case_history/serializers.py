from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CaseHistory
from apps.renewals.models import RenewalCase
User = get_user_model()
class CaseHistorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = CaseHistory
        fields = [
            'id',
            'action',
            'action_display',
            'description',
            'old_value',
            'new_value',
            'metadata',
            'created_at',
            'created_by',
            'created_by_name',
            'created_by_email',
        ]
        read_only_fields = ['id', 'created_at', 'created_by']
class CaseSerializer(serializers.ModelSerializer):
    handling_agent_name = serializers.SerializerMethodField()
    case_creation_method = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()
    current_status = serializers.SerializerMethodField()
    processing_time = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    started_at = serializers.DateTimeField(source='created_at', read_only=True)
    closed_at = serializers.SerializerMethodField()
    processing_days = serializers.SerializerMethodField()
    history = CaseHistorySerializer(source='case_history', many=True, read_only=True)
    is_closed = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalCase
        fields = [
            'id',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'handling_agent_name',
            'case_creation_method',
            'created_date',
            'current_status',
            'processing_time',
            'customer',
            'customer_name',
            'customer_email',
            'policy',
            'started_at',
            'closed_at',
            'processing_days',
            'renewal_amount',
            'payment_status',
            'batch_code',
            'is_closed',
            'is_active',
            'history',
            'comments',
            'created_by',
            'updated_by',
        ]
    
    def get_handling_agent_name(self, obj):
        if obj.policy and obj.policy.agent:
            return obj.policy.agent.agent_name
        return None
    
    def get_case_creation_method(self, obj):
        if obj.batch_code:
            return f"Case uploaded via bulk upload (Batch: {obj.batch_code})"
        else:
            return "Case created by agent"
    
    def get_created_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y, %I:%M:%S %p')
        return None
    
    def get_current_status(self, obj):
        from apps.case_logs.models import CaseLog
        last_case_log = CaseLog.objects.filter(
            renewal_case=obj, 
            is_deleted=False
        ).order_by('-created_at').first()
        
        if last_case_log and last_case_log.current_work_step:
            return last_case_log.get_current_work_step_display()
        return None
    
    def get_processing_time(self, obj):
        if obj.created_at:
            from django.utils import timezone
            now = timezone.now()
            if obj.created_at.tzinfo is None:
                case_created = timezone.make_aware(obj.created_at)
            else:
                case_created = obj.created_at
            delta = now - case_created
            return delta.days
        return None
    
    def get_closed_at(self, obj):
        if obj.status in ['completed', 'renewed', 'cancelled', 'expired']:
            return obj.updated_at
        return None
    
    def get_processing_days(self, obj):
        if obj.created_at:
            from django.utils import timezone
            now = timezone.now()
            if obj.created_at.tzinfo is None:
                created_at = timezone.make_aware(obj.created_at)
            else:
                created_at = obj.created_at
            delta = now - created_at
            return delta.days
        return 0
    
    def get_is_closed(self, obj):
        return obj.status in ['completed', 'renewed', 'cancelled', 'expired']
    
    def get_is_active(self, obj):
        return obj.status not in ['completed', 'renewed', 'cancelled', 'expired']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        case = super().create(validated_data)
        
        CaseHistory.objects.create(
            case=case,
            action='case_created',
            description=f"Case {case.case_id} created",
            created_by=self.context['request'].user
        )
        
        return case
    
    def update(self, instance, validated_data):
        old_status = instance.status
        old_agent = instance.handling_agent
        
        case = super().update(instance, validated_data)
        
        user = self.context['request'].user
        
        if old_status != case.status:
            CaseHistory.objects.create(
                case=case,
                action='status_changed',
                description=f"Status changed from {old_status} to {case.status}",
                old_value=old_status,
                new_value=case.status,
                created_by=user
            )
        
        if old_agent != case.handling_agent:
            if case.handling_agent:
                CaseHistory.objects.create(
                    case=case,
                    action='agent_assigned',
                    description=f"Case assigned to {case.handling_agent.get_full_name()}",
                    new_value=str(case.handling_agent.id),
                    created_by=user
                )
            else:
                CaseHistory.objects.create(
                    case=case,
                    action='agent_unassigned',
                    description="Case unassigned from agent",
                    old_value=str(old_agent.id) if old_agent else '',
                    created_by=user
                )
        
        return case


class CaseListSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source='case_number', read_only=True)
    title = serializers.SerializerMethodField()
    handling_agent_name = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    started_at = serializers.DateTimeField(source='created_at', read_only=True)
    processing_days = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    history_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalCase
        fields = [
            'id',
            'case_id',
            'title',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'handling_agent_name',
            'customer_name',
            'started_at',
            'processing_days',
            'comments_count',
            'history_count',
            'created_at',
        ]
    
    def get_title(self, obj):
        if obj.customer and obj.policy:
            return f"Renewal for {obj.customer.full_name} - {obj.policy.policy_number}"
        elif obj.customer:
            return f"Renewal for {obj.customer.full_name}"
        else:
            return f"Renewal Case {obj.case_number}"
    
    def get_handling_agent_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name()
        return None
    
    def get_processing_days(self, obj):
        if obj.created_at:
            from django.utils import timezone
            now = timezone.now()
            if obj.created_at.tzinfo is None:
                created_at = timezone.make_aware(obj.created_at)
            else:
                created_at = obj.created_at
            delta = now - created_at
            return delta.days
        return 0
    
    def get_comments_count(self, obj):
        return obj.case_comments.filter(is_deleted=False).count()
    
    def get_history_count(self, obj):
        return obj.case_history.filter(is_deleted=False).count()

class CaseStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenewalCase
        fields = ['status']
    
    def update(self, instance, validated_data):
        """Update case status and create history entry."""
        old_status = instance.status
        instance.status = validated_data['status']
        instance.save()
        
        CaseHistory.objects.create(
            case=instance,
            action='status_changed',
            description=f"Status changed from {old_status} to {instance.status}",
            old_value=old_status,
            new_value=instance.status,
            created_by=self.context['request'].user
        )
        
        return instance

class CaseAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenewalCase
        fields = ['handling_agent']
    
    def update(self, instance, validated_data):
        old_agent = instance.handling_agent
        instance.handling_agent = validated_data['handling_agent']
        instance.save()
        
        if instance.handling_agent:
            CaseHistory.objects.create(
                case=instance,
                action='agent_assigned',
                description=f"Case assigned to {instance.handling_agent.get_full_name()}",
                new_value=str(instance.handling_agent.id),
                created_by=self.context['request'].user
            )
        else:
            CaseHistory.objects.create(
                case=instance,
                action='agent_unassigned',
                description="Case unassigned from agent",
                old_value=str(old_agent.id) if old_agent else '',
                created_by=self.context['request'].user
            )
        
        return instance

class CaseTimelineSummarySerializer(serializers.ModelSerializer):    
    case_started = serializers.SerializerMethodField()
    current_status = serializers.SerializerMethodField()
    handling_agent = serializers.SerializerMethodField()
    processing_time = serializers.SerializerMethodField()
    journey_progress = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalCase
        fields = [
            'case_started',
            'current_status',
            'handling_agent',
            'processing_time',
            'journey_progress',
        ]
    
    def get_case_started(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return None
    
    def get_current_status(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_handling_agent(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return None
    
    def get_processing_time(self, obj):
        if obj.created_at:
            from django.utils import timezone
            now = timezone.now()
            if obj.created_at.tzinfo is None:
                case_created = timezone.make_aware(obj.created_at)
            else:
                case_created = obj.created_at
            delta = now - case_created
            return delta.days
        return None
    
    def get_journey_progress(self, obj):
        status_order = ['uploaded', 'assigned', 'in_progress', 'pending', 'renewed', 'completed']
        current_index = status_order.index(obj.status) if obj.status in status_order else -1
        
        progress = []
        for i, status_val in enumerate(status_order):
            if i <= current_index:
                progress.append({
                    'step': i + 1,
                    'status': status_val,
                    'status_display': obj.get_status_display() if obj.status == status_val else dict(RenewalCase.STATUS_CHOICES).get(status_val, status_val.title()),
                    'is_completed': i < current_index,
                    'is_current': i == current_index
                })
        
        return progress

class CaseTimelineHistorySerializer(serializers.ModelSerializer):
    event_type = serializers.CharField(source='get_action_display', read_only=True)
    event_description = serializers.CharField(source='description', read_only=True)
    event_date = serializers.SerializerMethodField()
    event_time = serializers.SerializerMethodField()
    performed_by = serializers.SerializerMethodField()
    
    class Meta:
        model = CaseHistory
        fields = [
            'event_type',
            'event_description',
            'event_date',
            'event_time',
            'performed_by',
        ]
    
    def get_event_date(self, obj):
        """Format date as DD/MM/YYYY"""
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return None
    
    def get_event_time(self, obj):
        """Format time as HH:MM:SS"""
        if obj.created_at:
            return obj.created_at.strftime('%H:%M:%S')
        return None
    
    def get_performed_by(self, obj):
        """Get user who performed the action"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return "System"


class UpdateCaseStatusSerializer(serializers.ModelSerializer):
    STATUS_MAPPING = {
        'Open': 'uploaded',
        'In Progress': 'in_progress',
        'Pending': 'pending',
        'Closed': 'renewed', 
        'Assigned': 'assigned',
        'Followup': 'pending',  
        'Failed': 'failed',
        'Renewed': 'renewed',
        'Not Intrested': 'not_interested',
        'DNC Email': 'dnc_email',
        'DNC WhatsApp': 'dnc_whatsapp',
        'DNC SMS': 'dnc_sms',
        'DNC Call': 'dnc_call',
        'DNC Bot Calling': 'dnc_bot_calling',
        'Payment Failed': 'payment_failed',
        'Customer Postponed': 'customer_postponed',
    }
    
    status = serializers.CharField(required=True)
    follow_up_date = serializers.DateField(required=False, allow_null=True)
    follow_up_time = serializers.TimeField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = RenewalCase
        fields = ['status', 'follow_up_date', 'follow_up_time', 'remarks']
    
    def validate_status(self, value):
        valid_db_values = [choice[0] for choice in RenewalCase.STATUS_CHOICES]
        if value in valid_db_values:
            return value
        
        mapped_value = self.STATUS_MAPPING.get(value)
        if not mapped_value:
            valid_options = list(self.STATUS_MAPPING.keys()) + valid_db_values
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(valid_options)}"
            )
        return mapped_value
    
    def validate_remarks(self, value):
        if value and value.strip() and len(value.strip()) < 10:
            raise serializers.ValidationError("Remarks must be at least 10 characters long.")
        return value
    
    def update(self, instance, validated_data):
        from .models import CaseHistory
        
        old_status = instance.status
        status_changed = False
        
        if 'status' in validated_data:
            new_status = validated_data['status']
            if old_status != new_status:
                instance.status = new_status
                status_changed = True
        
        if 'follow_up_date' in validated_data:
            instance.follow_up_date = validated_data['follow_up_date']
        
        if 'follow_up_time' in validated_data:
            instance.follow_up_time = validated_data['follow_up_time']
        
        if 'remarks' in validated_data:
            instance.remarks = validated_data['remarks']
        
        instance.save()
        
        if status_changed:
            CaseHistory.objects.create(
                case=instance,
                action='status_changed',
                description=f"Status changed from {old_status} to {instance.status}",
                old_value=old_status,
                new_value=instance.status,
                created_by=self.context['request'].user
            )
        
        if 'follow_up_date' in validated_data or 'follow_up_time' in validated_data:
            follow_up_info = []
            if instance.follow_up_date:
                follow_up_info.append(f"Follow-up date: {instance.follow_up_date}")
            if instance.follow_up_time:
                follow_up_info.append(f"Follow-up time: {instance.follow_up_time}")
            
            if follow_up_info:
                CaseHistory.objects.create(
                    case=instance,
                    action='follow_up_scheduled',
                    description="; ".join(follow_up_info),
                    created_by=self.context['request'].user
                )
        
        if 'remarks' in validated_data and validated_data['remarks']:
            CaseHistory.objects.create(
                case=instance,
                action='other',
                description=f"Remarks updated: {validated_data['remarks'][:100]}{'...' if len(validated_data['remarks']) > 100 else ''}",
                created_by=self.context['request'].user
            )
        
        return instance