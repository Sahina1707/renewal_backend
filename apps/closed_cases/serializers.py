from rest_framework import serializers
from apps.renewals.models import RenewalCase
from apps.customers.models import Customer
from apps.policies.models import Policy, PolicyType
from apps.channels.models import Channel
from apps.files_upload.models import FileUpload
from apps.uploads.models import FileUpload as UploadsFileUpload
from django.contrib.auth import get_user_model

User = get_user_model()


class ClosedCasesListSerializer(serializers.ModelSerializer):
    """Serializer for closed cases list view"""
    
    # Customer fields
    customer_name = serializers.SerializerMethodField()
    customer_profile = serializers.SerializerMethodField()
    customer_mobile = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_language = serializers.SerializerMethodField()
    
    # Policy fields
    policy_number = serializers.SerializerMethodField()
    policy_type_name = serializers.SerializerMethodField()
    policy_category = serializers.SerializerMethodField()
    premium_amount = serializers.SerializerMethodField()
    expiry_date = serializers.SerializerMethodField()
    policy_status = serializers.SerializerMethodField()
    
    # Channel and Agent fields
    channel_name = serializers.SerializerMethodField()
    channel_type = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    
    # Batch and Upload fields
    batch_id = serializers.CharField(source='batch_code', read_only=True)
    upload_date = serializers.SerializerMethodField()
    upload_filename = serializers.SerializerMethodField()
    
    # Additional fields
    calls_count = serializers.SerializerMethodField()
    renewal_date = serializers.SerializerMethodField()
    closed_date = serializers.SerializerMethodField()
    last_action = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalCase
        fields = [
            'id',
            'case_number',
            'status',
            'priority',
            'customer_name',
            'customer_profile',
            'customer_mobile',
            'customer_email',
            'customer_language',
            'policy_number',
            'policy_type_name',
            'policy_category',
            'premium_amount',
            'expiry_date',
            'policy_status',
            'channel_name',
            'channel_type',
            'agent_name',
            'batch_id',
            'upload_date',
            'upload_filename',
            'calls_count',
            'renewal_date',
            'closed_date',
            'last_action',
            'renewal_amount',
            'payment_status',
            'payment_date',
            'created_at',
            'updated_at',
        ]
    
    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None
    
    def get_customer_profile(self, obj):
        return obj.customer.profile if obj.customer else None
    
    def get_customer_mobile(self, obj):
        return obj.customer.phone if obj.customer else None
    
    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer else None
    
    def get_customer_language(self, obj):
        return obj.customer.preferred_language if obj.customer else None
    
    def get_policy_number(self, obj):
        return obj.policy.policy_number if obj.policy else None
    
    def get_policy_type_name(self, obj):
        return obj.policy.policy_type.name if obj.policy and obj.policy.policy_type else None
    
    def get_policy_category(self, obj):
        return obj.policy.policy_type.category if obj.policy and obj.policy.policy_type else None
    
    def get_premium_amount(self, obj):
        return obj.policy.premium_amount if obj.policy else None
    
    def get_expiry_date(self, obj):
        return obj.policy.end_date if obj.policy else None
    
    def get_policy_status(self, obj):
        return obj.policy.status if obj.policy else None
    
    def get_channel_name(self, obj):
        return obj.channel_id.name if obj.channel_id else None
    
    def get_channel_type(self, obj):
        return obj.channel_id.channel_type if obj.channel_id else None
    
    def get_agent_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()
        return None
    
    def get_upload_date(self, obj):
        # Try to get upload date from file_uploads table using batch_code
        try:
            file_upload = FileUpload.objects.filter(
                processing_result__batch_code=obj.batch_code
            ).first()
            return file_upload.created_at if file_upload else None
        except:
            return None
    
    def get_upload_filename(self, obj):
        # Try to get filename from file_uploads table using batch_code
        try:
            file_upload = FileUpload.objects.filter(
                processing_result__batch_code=obj.batch_code
            ).first()
            return file_upload.original_filename if file_upload else None
        except:
            return None
    
    def get_calls_count(self, obj):
        return obj.communication_attempts
    
    def get_renewal_date(self, obj):
        return obj.policy.renewal_date if obj.policy else None
    
    def get_closed_date(self, obj):
        # For renewed/completed cases, use the payment_date or updated_at
        if obj.status in ['completed', 'renewed'] and obj.payment_date:
            return obj.payment_date
        return obj.updated_at
    
    def get_last_action(self, obj):
        return obj.last_contact_date if obj.last_contact_date else obj.updated_at


class ClosedCasesDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual closed case view"""
    
    # Include all fields from list serializer plus additional details
    customer_details = serializers.SerializerMethodField()
    policy_details = serializers.SerializerMethodField()
    channel_details = serializers.SerializerMethodField()
    agent_details = serializers.SerializerMethodField()
    upload_details = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalCase
        fields = [
            'id',
            'case_number',
            'batch_code',
            'status',
            'priority',
            'renewal_amount',
            'payment_status',
            'payment_date',
            'communication_attempts',
            'last_contact_date',
            'notes',
            'created_at',
            'updated_at',
            'is_deleted',
            'deleted_at',
            'deleted_by',
            'created_by',
            'updated_by',
            # Detailed nested objects
            'customer_details',
            'policy_details',
            'channel_details',
            'agent_details',
            'upload_details',
        ]
    
    def get_customer_details(self, obj):
        if not obj.customer:
            return None
        
        customer = obj.customer
        return {
            'id': customer.id,
            'customer_code': customer.customer_code,
            'full_name': customer.full_name,
            'email': customer.email,
            'phone': customer.phone,
            'address': f"{customer.address_line1} {customer.address_line2}".strip(),
            'city': customer.city,
            'state': customer.state,
            'postal_code': customer.postal_code,
            'language': customer.preferred_language,
            'profile': customer.profile,
            'total_policies': customer.total_policies,
        }
    
    def get_policy_details(self, obj):
        if not obj.policy:
            return None
        
        policy = obj.policy
        return {
            'id': policy.id,
            'policy_number': policy.policy_number,
            'policy_type': policy.policy_type.name if policy.policy_type else None,
            'category': policy.policy_type.category if policy.policy_type else None,
            'start_date': policy.start_date,
            'end_date': policy.end_date,
            'renewal_date': policy.renewal_date,
            'premium_amount': policy.premium_amount,
            'sum_assured': policy.sum_assured,
            'status': policy.status,
            'agent_name': policy.agent_name,
            'agent_code': policy.agent_code,
        }
    
    def get_channel_details(self, obj):
        if not obj.channel_id:
            return None
        
        channel = obj.channel_id
        return {
            'id': channel.id,
            'channel_name': channel.name,
            'channel_type': channel.channel_type,
            'manager_name': channel.manager_name,
            'status': channel.status,
        }
    
    def get_agent_details(self, obj):
        if not obj.assigned_to:
            return None
        
        agent = obj.assigned_to
        return {
            'id': agent.id,
            'username': agent.username,
            'first_name': agent.first_name,
            'last_name': agent.last_name,
            'email': agent.email,
            'full_name': f"{agent.first_name} {agent.last_name}".strip(),
        }
    
    def get_upload_details(self, obj):
        try:
            file_upload = FileUpload.objects.filter(
                processing_result__batch_code=obj.batch_code
            ).first()
            
            if file_upload:
                return {
                    'id': file_upload.id,
                    'original_filename': file_upload.original_filename,
                    'file_size': file_upload.file_size,
                    'upload_status': file_upload.upload_status,
                    'total_records': file_upload.total_records,
                    'successful_records': file_upload.successful_records,
                    'failed_records': file_upload.failed_records,
                    'created_at': file_upload.created_at,
                    'uploaded_by': file_upload.uploaded_by.username if file_upload.uploaded_by else None,
                }
            return None
        except:
            return None
