from rest_framework import serializers
from .models import CustomerInstallment
class CustomerInstallmentSerializer(serializers.ModelSerializer):
    """Serializer for CustomerInstallment model"""
    
    customer_name = serializers.CharField(
        source='customer.full_name', 
        read_only=True,
        help_text="Customer full name"
    )
    customer_code = serializers.CharField(
        source='customer.customer_code', 
        read_only=True,
        help_text="Customer code"
    )
    case_number = serializers.CharField(
        source='renewal_case.case_number', 
        read_only=True,
        help_text="Renewal case number"
    )
    payment_transaction_id = serializers.CharField(
        source='payment.transaction_id', 
        read_only=True,
        help_text="Associated payment transaction ID"
    )
    payment_status = serializers.CharField(
        source='payment.payment_status', 
        read_only=True,
        help_text="Associated payment status"
    )
    
    class Meta:
        model = CustomerInstallment
        fields = [
            'id', 'customer', 'renewal_case', 'customer_name', 'customer_code', 
            'case_number', 'period', 'amount', 'due_date', 'status', 'payment', 
            'payment_transaction_id', 'payment_status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
class CustomerInstallmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CustomerInstallment records"""
    
    class Meta:
        model = CustomerInstallment
        fields = [
            'customer', 'renewal_case', 'period', 'amount', 
            'due_date', 'status', 'payment'
        ]

class CustomerInstallmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CustomerInstallment records"""
    
    class Meta:
        model = CustomerInstallment
        fields = [
            'customer', 'renewal_case', 'period', 'amount', 
            'due_date', 'status', 'payment'
        ]
        extra_kwargs = {
            'customer': {'required': False},
            'renewal_case': {'required': False},
            'period': {'required': False},
            'amount': {'required': False},
            'due_date': {'required': False},
        }


class OutstandingSummarySerializer(serializers.Serializer):
    """Serializer for outstanding amounts summary"""
    total_outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_installments = serializers.IntegerField()
    oldest_due_date = serializers.DateField(allow_null=True)
    latest_due_date = serializers.DateField(allow_null=True)
    average_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    pending_count = serializers.IntegerField()
    overdue_count = serializers.IntegerField()


class OutstandingInstallmentSerializer(serializers.ModelSerializer):
    """Serializer for outstanding installments with additional calculated fields"""
    days_overdue = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    case_number = serializers.CharField(source='renewal_case.case_number', read_only=True)
    policy_type = serializers.CharField(source='renewal_case.policy.policy_type.name', read_only=True)
    policy_number = serializers.CharField(source='renewal_case.policy.policy_number', read_only=True)
    
    class Meta:
        model = CustomerInstallment
        fields = [
            'id', 'period', 'amount', 'due_date', 'status', 'days_overdue', 
            'is_overdue', 'customer_name', 'customer_code', 'case_number', 
            'policy_type', 'policy_number', 'created_at'
        ]
    
    def get_days_overdue(self, obj):
        return obj.days_overdue()
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
