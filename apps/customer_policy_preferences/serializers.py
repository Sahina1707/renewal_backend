from rest_framework import serializers
from .models import CustomerPolicyPreference

class CustomerPolicyPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for CustomerPolicyPreference model"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    renewal_case_number = serializers.CharField(source='renewal_cases.case_number', read_only=True)
    preference_summary = serializers.CharField(read_only=True)
    budget_summary = serializers.CharField(read_only=True)
    add_ons_summary = serializers.CharField(read_only=True)
    is_premium_customer = serializers.BooleanField(read_only=True)
    preference_score = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CustomerPolicyPreference
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'customer_email',
            'renewal_cases',
            'renewal_case_number',
            'preferred_tenure',
            'coverage_type',
            'preferred_insurer',
            'add_ons',
            'payment_mode',
            'auto_renewal',
            'digital_policy',
            'communication_preference',
            'budget_range_min',
            'budget_range_max',
            'special_requirements',
            'created_by',
            'avoided_policy_types',  
            'preference_summary',
            'budget_summary',
            'add_ons_summary',
            'is_premium_customer',
            'preference_score',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_vy']


class CustomerPolicyPreferenceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CustomerPolicyPreference"""
    
    class Meta:
        model = CustomerPolicyPreference
        fields = [
            'customer',
            'renewal_cases',
            'preferred_tenure',
            'coverage_type',
            'preferred_insurer',
            'add_ons',
            'payment_mode',
            'auto_renewal',
            'digital_policy',
            'communication_preference',
            'budget_range_min',
            'budget_range_max',
            'special_requirements',
        ]
    
    def validate(self, data):
        """Validate the preference data"""
        customer = data.get('customer')
        renewal_cases = data.get('renewal_cases')
        
        if customer and renewal_cases:
            existing = CustomerPolicyPreference.objects.filter(
                customer=customer,
                renewal_cases=renewal_cases,
                is_deleted=False
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "Preference already exists for this customer and renewal case."
                )
        
        budget_min = data.get('budget_range_min')
        budget_max = data.get('budget_range_max')
        
        if budget_min and budget_max and budget_min > budget_max:
            raise serializers.ValidationError(
                "Minimum budget cannot be greater than maximum budget."
            )
        
        return data


class CustomerPolicyPreferenceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CustomerPolicyPreference"""
    
    class Meta:
        model = CustomerPolicyPreference
        fields = [
            'preferred_tenure',
            'coverage_type',
            'preferred_insurer',
            'add_ons',
            'payment_mode',
            'auto_renewal',
            'digital_policy',
            'communication_preference',
            'budget_range_min',
            'budget_range_max',
            'special_requirements',
        ]
    
    def validate(self, data):
        """Validate the preference data"""
        # Validate budget range
        budget_min = data.get('budget_range_min', self.instance.budget_range_min if self.instance else None)
        budget_max = data.get('budget_range_max', self.instance.budget_range_max if self.instance else None)
        
        if budget_min and budget_max and budget_min > budget_max:
            raise serializers.ValidationError(
                "Minimum budget cannot be greater than maximum budget."
            )
        
        return data
class CustomerPolicyPreferenceListSerializer(serializers.ModelSerializer):
    """Serializer for listing CustomerPolicyPreference with minimal data"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    renewal_case_number = serializers.CharField(source='renewal_cases.case_number', read_only=True)
    preference_summary = serializers.CharField(read_only=True)
    budget_summary = serializers.CharField(read_only=True)
    is_premium_customer = serializers.BooleanField(read_only=True)
    preference_score = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CustomerPolicyPreference
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'customer_email',
            'renewal_cases',
            'renewal_case_number',
            'preferred_tenure',
            'coverage_type',
            'preferred_insurer',
            'payment_mode',
            'auto_renewal',
            'digital_policy',
            'communication_preference',
            'budget_summary',
            'preference_summary',
            'is_premium_customer',
            'preference_score',
            'created_at',
        ]


class CustomerPolicyPreferenceSummarySerializer(serializers.ModelSerializer):
    """Serializer for preference summary and analytics"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    preference_summary = serializers.CharField(read_only=True)
    budget_summary = serializers.CharField(read_only=True)
    add_ons_summary = serializers.CharField(read_only=True)
    is_premium_customer = serializers.BooleanField(read_only=True)
    preference_score = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CustomerPolicyPreference
        fields = [
            'id',
            'customer_name',
            'customer_code',
            'coverage_type',
            'preferred_tenure',
            'payment_mode',
            'auto_renewal',
            'digital_policy',
            'preference_summary',
            'budget_summary',
            'add_ons_summary',
            'is_premium_customer',
            'preference_score',
            'created_at',
        ]
