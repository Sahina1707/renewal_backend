"""
Serializers for Claims app.
"""

from rest_framework import serializers
from .models import Claim
from apps.customers.models import Customer
from apps.policies.models import Policy


class ClaimSerializer(serializers.ModelSerializer):
    """Full serializer for Claim model with all fields"""
    
    # Auto-fetched customer fields
    customer_name = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    email_id = serializers.SerializerMethodField()
    
    # Foreign key fields
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.filter(is_deleted=False),
        source='customer',
        write_only=True,
        help_text="ID of the customer"
    )
    
    policy_id = serializers.PrimaryKeyRelatedField(
        queryset=Policy.objects.filter(is_deleted=False),
        source='policy',
        required=False,
        allow_null=True,
        write_only=True,
        help_text="ID of the policy"
    )
    
    # Display fields
    policy_number_display = serializers.CharField(
        source='policy.policy_number',
        read_only=True,
        help_text="Policy number from related policy"
    )
    
    class Meta:
        model = Claim
        fields = [
            'id',
            'claim_number',
            'customer_id',
            'customer_name',
            'mobile_number',
            'email_id',
            'policy_id',
            'policy_number',
            'policy_number_display',
            'insurance_company_name',
            'expire_date',
            'incident_date',
            'reported_date',
            'claim_type',
            'claim_amount',
            'description',
            'status',
            'remarks',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        ]
        read_only_fields = [
            'id',
            'claim_number',
            'customer_name',
            'mobile_number',
            'email_id',
            'policy_number_display',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        ]
    
    def get_customer_name(self, obj):
        """Get customer full name"""
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}".strip()
        return None
    
    def get_mobile_number(self, obj):
        """Get customer mobile number"""
        if obj.customer:
            return obj.customer.phone
        return None
    
    def get_email_id(self, obj):
        """Get customer email"""
        if obj.customer:
            return obj.customer.email
        return None
    
    def validate(self, data):
        """Validate the data"""
        # Auto-populate policy_number if policy is provided
        if 'policy' in data and data['policy'] and not data.get('policy_number'):
            data['policy_number'] = data['policy'].policy_number
        
        # Auto-populate expire_date if policy is provided
        if 'policy' in data and data['policy'] and not data.get('expire_date'):
            policy = data['policy']
            if hasattr(policy, 'expiry_date') and policy.expiry_date:
                data['expire_date'] = policy.expiry_date
            elif hasattr(policy, 'end_date') and policy.end_date:
                data['expire_date'] = policy.end_date
        
        return data


class ClaimListSerializer(serializers.ModelSerializer):
    """Serializer for listing claims (simplified)"""
    
    customer_name = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    email_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Claim
        fields = [
            'id',
            'claim_number',
            'customer_name',
            'mobile_number',
            'email_id',
            'policy_number',
            'insurance_company_name',
            'claim_type',
            'claim_amount',
            'status',
            'created_at',
        ]
    
    def get_customer_name(self, obj):
        """Get customer full name"""
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}".strip()
        return None
    
    def get_mobile_number(self, obj):
        """Get customer mobile number"""
        if obj.customer:
            return obj.customer.phone
        return None
    
    def get_email_id(self, obj):
        """Get customer email"""
        if obj.customer:
            return obj.customer.email
        return None


class ClaimCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating claims"""
    
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.filter(is_deleted=False),
        source='customer',
        help_text="ID of the customer"
    )
    
    policy_id = serializers.PrimaryKeyRelatedField(
        queryset=Policy.objects.filter(is_deleted=False),
        source='policy',
        required=False,
        allow_null=True,
        help_text="ID of the policy"
    )
    
    class Meta:
        model = Claim
        fields = [
            'customer_id',
            'policy_id',
            'insurance_company_name',
            'policy_number',
            'expire_date',
            'incident_date',
            'reported_date',
            'claim_type',
            'claim_amount',
            'description',
            'status',
            'remarks',
        ]
    
    def validate_customer_id(self, value):
        """Validate that the customer exists and is not deleted"""
        if not value:
            raise serializers.ValidationError("Customer ID is required.")
        
        if not Customer.objects.filter(id=value.id, is_deleted=False).exists():
            raise serializers.ValidationError(
                f"Customer with ID {value.id} does not exist or has been deleted. Please provide a valid customer_id."
            )
        return value
    
    def validate_policy_id(self, value):
        """Validate that the policy exists and is not deleted (if provided)"""
        if value:
            if not Policy.objects.filter(id=value.id, is_deleted=False).exists():
                raise serializers.ValidationError(
                    f"Policy with ID {value.id} does not exist or has been deleted. Please provide a valid policy_id."
                )
        return value
    
    def validate(self, data):
        """Validate the data"""
        # Auto-populate policy_number if policy is provided
        if 'policy' in data and data['policy'] and not data.get('policy_number'):
            data['policy_number'] = data['policy'].policy_number
        
        # Auto-populate expire_date if policy is provided
        if 'policy' in data and data['policy'] and not data.get('expire_date'):
            policy = data['policy']
            if hasattr(policy, 'expiry_date') and policy.expiry_date:
                data['expire_date'] = policy.expiry_date
            elif hasattr(policy, 'end_date') and policy.end_date:
                data['expire_date'] = policy.end_date
        
        return data

