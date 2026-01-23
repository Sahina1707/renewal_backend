from rest_framework import serializers
from .models import CustomerFinancialProfile
from apps.customers.models import Customer


class CustomerFinancialProfileSerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    income_range = serializers.CharField(read_only=True)
    capacity_status = serializers.CharField(read_only=True)
    recommended_premium = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerFinancialProfile
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'annual_income',
            'income_captured_date',
            'income_source',
            'policy_capacity_utilization',
            'recommended_policies_count',
            'recommended_policies_value',
            'risk_profile',
            'tolerance_score',
            'income_range',
            'capacity_status',
            'recommended_premium',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_recommended_premium(self, obj):
        return obj.calculate_recommended_premium()
    
    def validate_customer(self, value):
        if self.instance is None:  
            if CustomerFinancialProfile.objects.filter(customer=value, is_deleted=False).exists():
                raise serializers.ValidationError(
                    "Customer already has a financial profile."
                )
        return value


class CustomerFinancialProfileCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CustomerFinancialProfile
        fields = [
            'customer',
            'annual_income',
            'income_captured_date',
            'income_source',
            'policy_capacity_utilization',
            'recommended_policies_count',
            'recommended_policies_value',
            'risk_profile',
            'tolerance_score',
        ]
    
    def validate_customer(self, value):
        if CustomerFinancialProfile.objects.filter(customer=value, is_deleted=False).exists():
            raise serializers.ValidationError(
                "Customer already has a financial profile."
            )
        return value


class CustomerFinancialProfileUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CustomerFinancialProfile
        fields = [
            'annual_income',
            'income_captured_date',
            'income_source',
            'policy_capacity_utilization',
            'recommended_policies_count',
            'recommended_policies_value',
            'risk_profile',
            'tolerance_score',
        ]


class CustomerFinancialProfileListSerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    income_range = serializers.CharField(read_only=True)
    capacity_status = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerFinancialProfile
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'customer_email',
            'annual_income',
            'income_source',
            'risk_profile',
            'policy_capacity_utilization',
            'income_range',
            'capacity_status',
            'created_at',
        ]
