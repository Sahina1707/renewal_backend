from rest_framework import serializers
from decimal import Decimal
from .models import CustomerPayment
from apps.customers.models import Customer
from apps.renewals.models import RenewalCase
class CustomerPaymentSerializer(serializers.ModelSerializer):
    """Serializer for CustomerPayment model"""
    
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    customer_name = serializers.CharField(read_only=True)
    policy_number = serializers.CharField(read_only=True)
    case_number = serializers.CharField(source='renewal_case.case_number', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_successful = serializers.BooleanField(read_only=True)
    is_failed = serializers.BooleanField(read_only=True)
    is_pending = serializers.BooleanField(read_only=True)
    is_refunded = serializers.BooleanField(read_only=True)
    total_amount_with_fees = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    effective_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_summary = serializers.CharField(read_only=True)
    transaction_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerPayment
        fields = [
            'id',
            'customer_id',
            'customer_name',
            'policy_number',
            'case_number',
            'payment_amount',
            'payment_status',
            'payment_date',
            'payment_mode',
            'transaction_id',
            'gateway_response',
            'reference_number',
            'payment_gateway',
            'currency',
            'exchange_rate',
            'processing_fee',
            'tax_amount',
            'discount_amount',
            'net_amount',
            'attempt_count',
            'is_auto_payment',
            'failure_reason',
            'failure_code',
            'refund_amount',
            'refund_date',
            'refund_reference',
            'receipt_number',
            'receipt_url',
            'due_date',
            'grace_period_days',
            'payment_notes',
            'customer_remarks',
            'is_overdue',
            'days_overdue',
            'is_successful',
            'is_failed',
            'is_pending',
            'is_refunded',
            'total_amount_with_fees',
            'effective_amount',
            'payment_summary',
            'transaction_summary',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomerPaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CustomerPayment"""
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source="customer"   
    )
    renewal_case_id = serializers.PrimaryKeyRelatedField(
        queryset=RenewalCase.objects.all(),
        source="renewal_case"
    )
    class Meta:
        model = CustomerPayment
        fields = [
            'customer_id',
            'renewal_case_id',
            'payment_amount',
            'payment_status',
            'payment_date',
            'payment_mode',
            'transaction_id',
            'gateway_response',
            'reference_number',
            'payment_gateway',
            'currency',
            'exchange_rate',
            'processing_fee',
            'tax_amount',
            'discount_amount',
            'attempt_count',
            'is_auto_payment',
            'failure_reason',
            'failure_code',
            'receipt_number',
            'receipt_url',
            'due_date',
            'grace_period_days',
            'payment_notes',
            'customer_remarks',
        ]
    
    def validate(self, data):
        """Validate the payment data"""
        payment_amount = data.get('payment_amount')
        if payment_amount and payment_amount <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero."
            )
        
        # Validate processing fee
        processing_fee = data.get('processing_fee', Decimal('0.00'))
        if processing_fee < 0:
            raise serializers.ValidationError(
                "Processing fee cannot be negative."
            )
        
        # Validate tax amount
        tax_amount = data.get('tax_amount', Decimal('0.00'))
        if tax_amount < 0:
            raise serializers.ValidationError(
                "Tax amount cannot be negative."
            )
        
        # Validate discount amount
        discount_amount = data.get('discount_amount', Decimal('0.00'))
        if discount_amount < 0:
            raise serializers.ValidationError(
                "Discount amount cannot be negative."
            )
        
        # Validate discount doesn't exceed payment amount
        if discount_amount > payment_amount:
            raise serializers.ValidationError(
                "Discount amount cannot exceed payment amount."
            )
        
        # Validate exchange rate
        exchange_rate = data.get('exchange_rate', Decimal('1.0000'))
        if exchange_rate <= 0:
            raise serializers.ValidationError(
                "Exchange rate must be greater than zero."
            )
        
        # Validate attempt count
        attempt_count = data.get('attempt_count', 1)
        if attempt_count < 1:
            raise serializers.ValidationError(
                "Attempt count must be at least 1."
            )
        
        return data
    
    def create(self, validated_data):
        """Create payment and calculate net amount"""
        payment = CustomerPayment(**validated_data)
        payment.calculate_net_amount()
        payment.save()
        return payment

class CustomerPaymentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CustomerPayment"""
    
    class Meta:
        model = CustomerPayment
        fields = [
            'payment_status',
            'payment_date',
            'payment_mode',
            'gateway_response',
            'reference_number',
            'payment_gateway',
            'processing_fee',
            'tax_amount',
            'discount_amount',
            'attempt_count',
            'failure_reason',
            'failure_code',
            'refund_amount',
            'refund_date',
            'refund_reference',
            'receipt_number',
            'receipt_url',
            'due_date',
            'grace_period_days',
            'payment_notes',
            'customer_remarks',
        ]
    
    def validate(self, data):
        """Validate the payment update data"""
        instance = self.instance
        
        # Validate refund amount
        refund_amount = data.get('refund_amount', instance.refund_amount if instance else Decimal('0.00'))
        payment_amount = instance.payment_amount if instance else Decimal('0.00')
        
        if refund_amount > payment_amount:
            raise serializers.ValidationError(
                "Refund amount cannot exceed payment amount."
            )
        
        # Validate processing fee
        processing_fee = data.get('processing_fee', instance.processing_fee if instance else Decimal('0.00'))
        if processing_fee < 0:
            raise serializers.ValidationError(
                "Processing fee cannot be negative."
            )
        
        # Validate tax amount
        tax_amount = data.get('tax_amount', instance.tax_amount if instance else Decimal('0.00'))
        if tax_amount < 0:
            raise serializers.ValidationError(
                "Tax amount cannot be negative."
            )
        
        # Validate discount amount
        discount_amount = data.get('discount_amount', instance.discount_amount if instance else Decimal('0.00'))
        if discount_amount < 0:
            raise serializers.ValidationError(
                "Discount amount cannot be negative."
            )
        
        if discount_amount > payment_amount:
            raise serializers.ValidationError(
                "Discount amount cannot exceed payment amount."
            )
        
        return data
    
    def update(self, instance, validated_data):
        """Update payment and recalculate net amount"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Recalculate net amount if financial fields changed
        financial_fields = ['processing_fee', 'tax_amount', 'discount_amount']
        if any(field in validated_data for field in financial_fields):
            instance.calculate_net_amount()
        
        instance.save()
        return instance


class CustomerPaymentListSerializer(serializers.ModelSerializer):
    """Serializer for listing CustomerPayment with minimal data"""
    
    customer_name = serializers.CharField(read_only=True)
    policy_number = serializers.CharField(read_only=True)
    case_number = serializers.CharField(source='renewal_case.case_number', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    payment_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerPayment
        fields = [
            'id',
            'customer_id',
            'customer_name',
            'policy_number',
            'case_number',
            'payment_amount',
            'payment_status',
            'payment_date',
            'payment_mode',
            'transaction_id',
            'reference_number',
            'due_date',
            'is_overdue',
            'days_overdue',
            'payment_summary',
            'created_at',
        ]


class CustomerPaymentSummarySerializer(serializers.ModelSerializer):
    """Serializer for payment summary and analytics"""
    
    customer_name = serializers.CharField(read_only=True)
    policy_number = serializers.CharField(read_only=True)
    case_number = serializers.CharField(source='renewal_case.case_number', read_only=True)
    payment_summary = serializers.CharField(read_only=True)
    transaction_summary = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerPayment
        fields = [
            'id',
            'customer_name',
            'policy_number',
            'case_number',
            'payment_amount',
            'payment_status',
            'payment_mode',
            'transaction_id',
            'payment_date',
            'payment_summary',
            'transaction_summary',
            'created_at',
        ]


class PaymentRefundSerializer(serializers.Serializer):
    """Serializer for processing payment refunds"""
    
    refund_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    refund_reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    refund_reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    def validate_refund_amount(self, value):
        """Validate refund amount against payment amount"""
        payment = self.context.get('payment')
        if payment and value > payment.payment_amount:
            raise serializers.ValidationError(
                "Refund amount cannot exceed payment amount."
            )
        return value


class PaymentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating payment status"""
    
    payment_status = serializers.ChoiceField(
        choices=CustomerPayment.PAYMENT_STATUS_CHOICES
    )
    transaction_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    failure_reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    failure_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True
    )
    gateway_response = serializers.CharField(
        required=False,
        allow_blank=True
    )
    
    def validate(self, data):
        """Validate status update data"""
        payment_status = data.get('payment_status')
        
        # Require failure details for failed status
        if payment_status == 'failed':
            if not data.get('failure_reason') and not data.get('failure_code'):
                raise serializers.ValidationError(
                    "Failure reason or failure code is required for failed payments."
                )
        
        # Require transaction details for completed status
        if payment_status == 'completed':
            if not data.get('transaction_id') and not data.get('reference_number'):
                raise serializers.ValidationError(
                    "Transaction ID or reference number is required for completed payments."
                )
        
        return data
