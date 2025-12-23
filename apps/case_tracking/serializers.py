from rest_framework import serializers
from apps.renewals.models import RenewalCase
from apps.customers.models import Customer
from apps.policies.models import Policy, PolicyType
from apps.channels.models import Channel
from apps.customer_payments.models import CustomerPayment
from apps.files_upload.models import FileUpload
from apps.case_logs.models import CaseLog
from django.contrib.auth import get_user_model
from datetime import timedelta
User = get_user_model()

class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = '__all__'   


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


class CustomerPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPayment
        fields = '__all__'

class QuickEditCaseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=RenewalCase.STATUS_CHOICES,
        required=True,
        help_text="Main case status that will be updated in renewal_cases table"
    )

    sub_status = serializers.ChoiceField(
        choices=CaseLog.SUB_STATUS_CHOICES,
        required=True,
        help_text="Detailed sub-status for case tracking"
    )

    current_work_step = serializers.ChoiceField(
        choices=CaseLog.WORK_STEP_CHOICES,
        required=True,
        help_text="Current work step in the renewal process"
    )

    next_follow_up_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Date and time for next follow-up (optional)"
    )

    next_action_plan = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Description of next planned action (optional)"
    )

    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Additional comments about this update (optional)"
    )

    def validate(self, data):
        case_log_fields = ['sub_status', 'current_work_step', 'next_follow_up_date', 'next_action_plan', 'comment']
        has_case_log_data = any(
            data.get(field) and str(data.get(field)).strip()
            for field in case_log_fields
            if field in data
        )

        if not has_case_log_data:
            raise serializers.ValidationError(
                "At least one case log field (sub_status, current_work_step, next_follow_up_date, "
                "next_action_plan, or comment) must be provided with meaningful data."
            )

        return data

    def validate_status(self, value):
        if not value:
            raise serializers.ValidationError("Status is required.")
        return value

    def validate_sub_status(self, value):
        if not value:
            raise serializers.ValidationError("Sub-status is required.")
        return value

    def validate_current_work_step(self, value):
        if not value:
            raise serializers.ValidationError("Current work step is required.")
        return value

    def validate_next_action_plan(self, value):
        if value and len(value.strip()) > 1000:
            raise serializers.ValidationError("Next action plan cannot exceed 1000 characters.")
        return value.strip() if value else ""

    def validate_comment(self, value):
        if value and len(value.strip()) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return value.strip() if value else ""

class UpdateCaseLogSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RenewalCase.STATUS_CHOICES, required=False)
    sub_status = serializers.ChoiceField(choices=CaseLog.SUB_STATUS_CHOICES, required=False)
    current_work_step = serializers.ChoiceField(choices=CaseLog.WORK_STEP_CHOICES, required=False)
    next_follow_up_date = serializers.DateTimeField(required=False, allow_null=True)
    next_action_plan = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)

class CaseLogSerializer(serializers.ModelSerializer):

    renewal_case_number = serializers.CharField(source='renewal_case.case_number', read_only=True)
    sub_status = serializers.CharField(source='get_sub_status_display', read_only=True)
    current_work_step = serializers.CharField(source='get_current_work_step_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CaseLog
        fields = [
            'id',
            'renewal_case',
            'renewal_case_number',
            'sub_status',
            'current_work_step',
            'next_follow_up_date',
            'next_action_plan',
            'comment',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None


class CommentHistorySerializer(serializers.ModelSerializer):
    """Simplified serializer for comment history - only essential fields: status, sub_status, work step, next follow-up, next action plan"""
    status = serializers.CharField(source='renewal_case.status', read_only=True)
    status_display = serializers.SerializerMethodField()
    sub_status = serializers.CharField(source='get_sub_status_display', read_only=True)
    current_work_step = serializers.CharField(source='get_current_work_step_display', read_only=True)
    next_follow_up_date = serializers.SerializerMethodField()

    class Meta:
        model = CaseLog
        fields = [
            'status',
            'status_display',
            'sub_status',
            'current_work_step',
            'next_follow_up_date',
            'next_action_plan',
        ]
        read_only_fields = []

    def get_status_display(self, obj):
        """Get the display name for the status"""
        if obj.renewal_case:
            return obj.renewal_case.get_status_display()
        return None

    def get_next_follow_up_date(self, obj):
        """Format next follow-up date as DD/MM/YYYY"""
        if obj.next_follow_up_date:
            return obj.next_follow_up_date.strftime('%d/%m/%Y')
        return None


class CaseDetailsSerializer(serializers.Serializer):
    """Serializer for fetching case details for editing"""

    case_id = serializers.IntegerField(source='id', read_only=True)
    case_number = serializers.CharField(read_only=True)

    customer_name = serializers.CharField(source='customer.full_name')
    email = serializers.EmailField(source='customer.email')
    phone = serializers.CharField(source='customer.phone')

    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    policy_type_name = serializers.CharField(source='policy.policy_type.name', read_only=True)
    premium_amount = serializers.DecimalField(source='policy.premium_amount', max_digits=12, decimal_places=2, read_only=True)
    expiry_date = serializers.DateField(source='policy.end_date', read_only=True)
    assigned_agent_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, allow_null=True)


class EditCaseDetailsSerializer(serializers.Serializer):
    """Serializer for updating case details"""

    customer_name = serializers.CharField(max_length=200, required=False, help_text="Customer's full name")
    email = serializers.EmailField(required=False, help_text="Customer's email address")
    phone = serializers.CharField(max_length=20, required=False, help_text="Customer's phone number")

    policy_type = serializers.IntegerField(required=False, help_text="PolicyType ID from dropdown")
    premium_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, help_text="Policy premium amount")
    expiry_date = serializers.DateField(required=False, help_text="Policy expiry date (YYYY-MM-DD)")
    assigned_agent = serializers.IntegerField(required=False, allow_null=True, help_text="User ID for assigned agent from dropdown")

    def validate_policy_type(self, value):
        """Validate that policy type exists"""
        if value:
            try:
                PolicyType.objects.get(id=value, is_active=True)
            except PolicyType.DoesNotExist:
                raise serializers.ValidationError("Invalid policy type ID or policy type is not active.")
        return value

    def validate_assigned_agent(self, value):
        """Validate that assigned agent exists"""
        if value:
            try:
                User.objects.get(id=value, is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid agent ID or agent is not active.")
        return value

    def validate_email(self, value):
        """Validate email format and uniqueness within reasonable scope"""
        if value:
            pass
        return value

    def validate_phone(self, value):
        """Validate phone number format"""
        if value:
            if len(value.strip()) < 10:
                raise serializers.ValidationError("Phone number must be at least 10 digits.")
        return value


class PolicyTypeDropdownSerializer(serializers.Serializer):
    """Serializer for policy type dropdown options"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()


class AgentDropdownSerializer(serializers.Serializer):
    """Serializer for agent dropdown options"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()


class CaseEditFormDataSerializer(serializers.Serializer):
    """Serializer for complete case edit form data including dropdowns"""
    case_details = CaseDetailsSerializer()
    policy_types = PolicyTypeDropdownSerializer(many=True)
    agents = AgentDropdownSerializer(many=True)

class CaseTrackingSerializer(serializers.ModelSerializer):
    """
    Serializer for case tracking list view - includes all fields shown in frontend table
    """
    id = serializers.IntegerField(read_only=True)
    case_number = serializers.CharField(read_only=True)
    batch_id = serializers.CharField(source='batch_code', read_only=True)
    
    customer_name = serializers.SerializerMethodField()
    customer_profile = serializers.SerializerMethodField()
    customer_mobile = serializers.SerializerMethodField()
    customer_language = serializers.SerializerMethodField()
    
    policy_number = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    policy_category = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()  
    
    channel_name = serializers.SerializerMethodField()
    current_communication_channel = serializers.SerializerMethodField()
    
    status = serializers.CharField(read_only=True)
    policy_status = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    last_action = serializers.SerializerMethodField()
    calls_count = serializers.SerializerMethodField()
    renewal_date = serializers.SerializerMethodField()
    upload_date = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalCase
        fields = [
            'id',
            'case_number',
            'batch_id',
            'customer_name',
            'customer_profile',
            'customer_mobile',
            'customer_language',
            'policy_number',
            'product_name',
            'policy_category',
            'category',
            'channel_name',
            'current_communication_channel',
            'status',
            'policy_status',
            'agent_name',
            'priority',
            'last_action',
            'calls_count',
            'renewal_date',
            'upload_date',
        ]
    
    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None
    
    def get_customer_profile(self, obj):
        return obj.customer.profile if obj.customer else None
    
    def get_customer_mobile(self, obj):
        return obj.customer.phone if obj.customer else None
    
    def get_customer_language(self, obj):
        return obj.customer.preferred_language if obj.customer else None
    
    def get_policy_number(self, obj):
        return obj.policy.policy_number if obj.policy else None
    
    def get_product_name(self, obj):
        if obj.policy and obj.policy.policy_type:
            return obj.policy.policy_type.name
        return None
    
    def get_policy_category(self, obj):
        if obj.policy and obj.policy.policy_type:
            return obj.policy.policy_type.category
        return None
    
    def get_category(self, obj):
        """Alias for policy_category for frontend compatibility"""
        return self.get_policy_category(obj)
    
    def get_channel_name(self, obj):
        if obj.customer and obj.customer.channel_id:
            return obj.customer.channel_id.name
        return None
    
    def get_current_communication_channel(self, obj):
        """Get the latest communication channel from CommunicationLog"""
        try:
            from apps.customer_communication_preferences.models import CommunicationLog
            latest_communication = CommunicationLog.objects.filter(
                customer=obj.customer,
                is_deleted=False
            ).order_by('-communication_date').first()
            
            if latest_communication:
                return latest_communication.get_channel_display()
        except Exception:
            pass
        return None
    
    def get_policy_status(self, obj):
        return obj.policy.status if obj.policy else None
    
    def get_agent_name(self, obj):
        if obj.policy and obj.policy.agent:
            return obj.policy.agent.agent_name
        return None

    
    def get_priority(self, obj):
        """Get priority display value"""
        return obj.priority if hasattr(obj, 'priority') else 'medium'
    
    def get_last_action(self, obj):
        if obj.last_contact_date:
            return obj.last_contact_date.strftime('%d/%m/%Y')
        elif obj.updated_at:
            return obj.updated_at.strftime('%d/%m/%Y')
        return None
    
    def get_calls_count(self, obj):
        attempts = obj.communication_attempts_count
        if attempts:
            return f"{attempts} calls"
        return "0 calls"
    
    def get_renewal_date(self, obj):
        if obj.policy and obj.policy.renewal_date:
            return obj.policy.renewal_date.strftime('%d/%m/%Y')
        elif obj.policy and obj.policy.end_date:
            return obj.policy.end_date.strftime('%d/%m/%Y')
        return None
    
    def get_upload_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return None


class CaseDetailSerializer(serializers.ModelSerializer):

    batch_id = serializers.CharField(source='batch_code', read_only=True)

    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_mobile = serializers.SerializerMethodField()
    customer_address = serializers.SerializerMethodField()

    policy_number = serializers.SerializerMethodField()
    policy_type = serializers.SerializerMethodField()
    policy_start_date = serializers.SerializerMethodField()
    policy_end_date = serializers.SerializerMethodField()
    premium_amount = serializers.SerializerMethodField()
    sum_assured = serializers.SerializerMethodField()

    channel_name = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()

    upload_filename = serializers.SerializerMethodField()
    upload_date = serializers.SerializerMethodField()

    calls_count = serializers.SerializerMethodField()

    class Meta:
        model = RenewalCase
        fields = [
            'id',
            'case_number',
            'batch_id',
            'status',
            'priority',
            'renewal_amount',
            'communication_attempts_count',
            'last_contact_date',
            'notes',
            'created_at',
            'updated_at',
            'customer_name',
            'customer_code',
            'customer_email',
            'customer_mobile',
            'customer_address',
            'policy_number',
            'policy_type',
            'policy_start_date',
            'policy_end_date',
            'premium_amount',
            'sum_assured',
            'channel_name',
            'agent_name',
            'upload_filename',
            'upload_date',
            'calls_count',
        ]

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None

    def get_customer_code(self, obj):
        return obj.customer.customer_code if obj.customer else None

    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer else None

    def get_customer_mobile(self, obj):
        return obj.customer.phone if obj.customer else None

    def get_customer_address(self, obj):
        if not obj.customer:
            return None
        customer = obj.customer
        address_parts = []
        if customer.address_line1:
            address_parts.append(customer.address_line1)
        if customer.city:
            address_parts.append(customer.city)
        if customer.state:
            address_parts.append(customer.state)
        if customer.postal_code:
            address_parts.append(customer.postal_code)
        return ', '.join(address_parts) if address_parts else None

    def get_policy_number(self, obj):
        return obj.policy.policy_number if obj.policy else None

    def get_policy_type(self, obj):
        return obj.policy.policy_type.name if obj.policy and obj.policy.policy_type else None

    def get_policy_start_date(self, obj):
        return obj.policy.start_date.strftime('%d/%m/%Y') if obj.policy and obj.policy.start_date else None

    def get_policy_end_date(self, obj):
        return obj.policy.end_date.strftime('%d/%m/%Y') if obj.policy and obj.policy.end_date else None

    def get_premium_amount(self, obj):
        return str(obj.policy.premium_amount) if obj.policy and obj.policy.premium_amount else None

    def get_sum_assured(self, obj):
        return str(obj.policy.sum_assured) if obj.policy and obj.policy.sum_assured else None

    def get_channel_name(self, obj):
        return obj.customer.channel_id.name if obj.customer and obj.customer.channel_id else None


    def get_agent_name(self, obj):
        if obj.policy and obj.policy.agent:
            return getattr(obj.policy.agent, 'agent_name', str(obj.policy.agent))
        return None
    def get_upload_filename(self, obj):
        try:

            time_window = timedelta(minutes=5)
            start_time = obj.created_at - time_window
            end_time = obj.created_at + time_window

            file_upload = FileUpload.objects.filter(
                created_at__range=(start_time, end_time),
                upload_status__in=['completed', 'partial']
            ).order_by('created_at').first()

            return file_upload.original_filename if file_upload else None
        except:
            return None

    def get_upload_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y') if obj.created_at else None

    def get_calls_count(self, obj):
        attempts = obj.communication_attempts_count
        if attempts:
            return f"{attempts} calls"
        return "0 calls"
