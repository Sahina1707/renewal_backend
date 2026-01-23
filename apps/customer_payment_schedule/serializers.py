from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from .models import PaymentSchedule
class PaymentScheduleSerializer(serializers.ModelSerializer):
    """Serializer for PaymentSchedule model"""
    
    customer_name = serializers.CharField(read_only=True)
    policy_number = serializers.CharField(read_only=True)
    case_number = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_due_today = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    is_eligible_for_early_discount = serializers.BooleanField(read_only=True)
    applicable_late_fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discounted_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_fully_paid = serializers.BooleanField(read_only=True)
    is_partially_paid = serializers.BooleanField(read_only=True)
    payment_progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    can_retry = serializers.BooleanField(read_only=True)
    schedule_summary = serializers.CharField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'id',
            'renewal_case',
            'customer_name',
            'policy_number',
            'case_number',
            'due_date',
            'amount_due',
            'status',
            'payment_method',
            'installment_number',
            'total_installments',
            'description',
            'reminder_sent',
            'reminder_date',
            'reminder_count',
            'auto_payment_enabled',
            'auto_payment_method',
            'payment_gateway',
            'gateway_schedule_id',
            'grace_period_days',
            'late_fee_applicable',
            'late_fee_amount',
            'late_fee_percentage',
            'early_payment_discount',
            'early_payment_days',
            'processed_date',
            'processed_amount',
            'transaction_reference',
            'failure_reason',
            'failure_code',
            'retry_count',
            'max_retry_attempts',
            'next_retry_date',
            'original_due_date',
            'reschedule_reason',
            'reschedule_count',
            'customer_notified',
            'notification_date',
            'customer_acknowledgment',
            'internal_notes',
            'customer_notes',
            'is_overdue',
            'days_overdue',
            'is_due_today',
            'days_until_due',
            'is_eligible_for_early_discount',
            'applicable_late_fee',
            'total_amount_due',
            'discounted_amount',
            'remaining_amount',
            'is_fully_paid',
            'is_partially_paid',
            'payment_progress_percentage',
            'can_retry',
            'schedule_summary',
            'status_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentScheduleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating PaymentSchedule"""
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'renewal_case',
            'due_date',
            'amount_due',
            'status',
            'payment_method',
            'installment_number',
            'total_installments',
            'description',
            'reminder_date',
            'auto_payment_enabled',
            'auto_payment_method',
            'payment_gateway',
            'gateway_schedule_id',
            'grace_period_days',
            'late_fee_applicable',
            'late_fee_amount',
            'late_fee_percentage',
            'early_payment_discount',
            'early_payment_days',
            'max_retry_attempts',
            'internal_notes',
            'customer_notes',
        ]
    
    def validate(self, data):
        """Validate the payment schedule data"""
        amount_due = data.get('amount_due')
        if amount_due and amount_due <= 0:
            raise serializers.ValidationError(
                "Amount due must be greater than zero."
            )
        
        installment_number = data.get('installment_number', 1)
        total_installments = data.get('total_installments', 1)
        
        if installment_number < 1:
            raise serializers.ValidationError(
                "Installment number must be at least 1."
            )
        
        if total_installments < 1:
            raise serializers.ValidationError(
                "Total installments must be at least 1."
            )
        
        if installment_number > total_installments:
            raise serializers.ValidationError(
                "Installment number cannot exceed total installments."
            )
        
        late_fee_amount = data.get('late_fee_amount', Decimal('0.00'))
        late_fee_percentage = data.get('late_fee_percentage', Decimal('0.00'))
        
        if late_fee_amount < 0:
            raise serializers.ValidationError(
                "Late fee amount cannot be negative."
            )
        
        if late_fee_percentage < 0 or late_fee_percentage > 100:
            raise serializers.ValidationError(
                "Late fee percentage must be between 0 and 100."
            )
        
        early_payment_discount = data.get('early_payment_discount', Decimal('0.00'))
        early_payment_days = data.get('early_payment_days', 0)
        
        if early_payment_discount < 0:
            raise serializers.ValidationError(
                "Early payment discount cannot be negative."
            )
        
        if early_payment_discount > amount_due:
            raise serializers.ValidationError(
                "Early payment discount cannot exceed amount due."
            )
        
        if early_payment_days < 0:
            raise serializers.ValidationError(
                "Early payment days cannot be negative."
            )
        
        grace_period_days = data.get('grace_period_days', 0)
        if grace_period_days < 0:
            raise serializers.ValidationError(
                "Grace period days cannot be negative."
            )
        
        max_retry_attempts = data.get('max_retry_attempts', 3)
        if max_retry_attempts < 0:
            raise serializers.ValidationError(
                "Max retry attempts cannot be negative."
            )
        
        due_date = data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise serializers.ValidationError(
                "Due date cannot be in the past."
            )
        
        auto_payment_enabled = data.get('auto_payment_enabled', False)
        auto_payment_method = data.get('auto_payment_method', '')
        
        if auto_payment_enabled and not auto_payment_method:
            raise serializers.ValidationError(
                "Auto payment method is required when auto payment is enabled."
            )
        
        return data
class PaymentScheduleUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating PaymentSchedule"""
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'due_date',
            'amount_due',
            'status',
            'payment_method',
            'description',
            'reminder_date',
            'auto_payment_enabled',
            'auto_payment_method',
            'payment_gateway',
            'gateway_schedule_id',
            'grace_period_days',
            'late_fee_applicable',
            'late_fee_amount',
            'late_fee_percentage',
            'early_payment_discount',
            'early_payment_days',
            'processed_amount',
            'transaction_reference',
            'failure_reason',
            'failure_code',
            'max_retry_attempts',
            'next_retry_date',
            'reschedule_reason',
            'customer_acknowledgment',
            'internal_notes',
            'customer_notes',
        ]
    
    def validate(self, data):
        """Validate the payment schedule update data"""
        instance = self.instance
        
        amount_due = data.get('amount_due', instance.amount_due if instance else Decimal('0.00'))
        if amount_due <= 0:
            raise serializers.ValidationError(
                "Amount due must be greater than zero."
            )
        
        processed_amount = data.get('processed_amount', instance.processed_amount if instance else Decimal('0.00'))
        if processed_amount < 0:
            raise serializers.ValidationError(
                "Processed amount cannot be negative."
            )
        
        if processed_amount > amount_due:
            raise serializers.ValidationError(
                "Processed amount cannot exceed amount due."
            )
        
        late_fee_amount = data.get('late_fee_amount', instance.late_fee_amount if instance else Decimal('0.00'))
        late_fee_percentage = data.get('late_fee_percentage', instance.late_fee_percentage if instance else Decimal('0.00'))
        
        if late_fee_amount < 0:
            raise serializers.ValidationError(
                "Late fee amount cannot be negative."
            )
        
        if late_fee_percentage < 0 or late_fee_percentage > 100:
            raise serializers.ValidationError(
                "Late fee percentage must be between 0 and 100."
            )
        
        early_payment_discount = data.get('early_payment_discount', instance.early_payment_discount if instance else Decimal('0.00'))
        
        if early_payment_discount < 0:
            raise serializers.ValidationError(
                "Early payment discount cannot be negative."
            )
        
        if early_payment_discount > amount_due:
            raise serializers.ValidationError(
                "Early payment discount cannot exceed amount due."
            )
        
        return data

class PaymentScheduleListSerializer(serializers.ModelSerializer):
    """Serializer for listing PaymentSchedule with minimal data"""
    
    customer_name = serializers.CharField(read_only=True)
    policy_number = serializers.CharField(read_only=True)
    case_number = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    schedule_summary = serializers.CharField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'id',
            'renewal_case',
            'customer_name',
            'policy_number',
            'case_number',
            'due_date',
            'amount_due',
            'status',
            'payment_method',
            'installment_number',
            'total_installments',
            'auto_payment_enabled',
            'is_overdue',
            'days_until_due',
            'schedule_summary',
            'status_display',
            'created_at',
        ]

class PaymentScheduleSummarySerializer(serializers.ModelSerializer):
    """Serializer for payment schedule summary and analytics"""
    
    customer_name = serializers.CharField(read_only=True)
    policy_number = serializers.CharField(read_only=True)
    case_number = serializers.CharField(read_only=True)
    schedule_summary = serializers.CharField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'id',
            'customer_name',
            'policy_number',
            'case_number',
            'due_date',
            'amount_due',
            'status',
            'installment_number',
            'total_installments',
            'schedule_summary',
            'status_display',
            'created_at',
        ]


class PaymentProcessingSerializer(serializers.Serializer):
    """Serializer for processing scheduled payments"""
    
    processed_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    transaction_reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    payment_gateway = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True
    )
    gateway_response = serializers.CharField(
        required=False,
        allow_blank=True
    )
    
    def validate_processed_amount(self, value):
        """Validate processed amount against scheduled amount"""
        schedule = self.context.get('schedule')
        if schedule and value > schedule.amount_due:
            raise serializers.ValidationError(
                "Processed amount cannot exceed scheduled amount."
            )
        return value


class PaymentRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling payments"""
    
    new_due_date = serializers.DateField()
    reschedule_reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    def validate_new_due_date(self, value):
        """Validate new due date"""
        if value < timezone.now().date():
            raise serializers.ValidationError(
                "New due date cannot be in the past."
            )
        return value


class PaymentFailureSerializer(serializers.Serializer):
    """Serializer for marking payment as failed"""
    
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
    schedule_retry = serializers.BooleanField(
        default=True,
        help_text="Whether to schedule automatic retry"
    )

class AutoPaymentSerializer(serializers.Serializer):
    """Serializer for auto payment settings"""
    
    auto_payment_enabled = serializers.BooleanField()
    auto_payment_method = serializers.ChoiceField(
        choices=PaymentSchedule.PAYMENT_METHOD_CHOICES,
        required=False,
        allow_blank=True
    )
    payment_gateway = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True
    )
    gateway_schedule_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    
    def validate(self, data):
        """Validate auto payment settings"""
        auto_payment_enabled = data.get('auto_payment_enabled')
        auto_payment_method = data.get('auto_payment_method')
        
        if auto_payment_enabled and not auto_payment_method:
            raise serializers.ValidationError(
                "Auto payment method is required when auto payment is enabled."
            )
        
        return data


class BulkScheduleCreateSerializer(serializers.Serializer):
    """Serializer for creating multiple payment schedules"""
    
    renewal_case = serializers.IntegerField()
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    installment_count = serializers.IntegerField(min_value=1, max_value=12)
    first_due_date = serializers.DateField()
    payment_method = serializers.ChoiceField(
        choices=PaymentSchedule.PAYMENT_METHOD_CHOICES
    )
    payment_frequency = serializers.ChoiceField(
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('half_yearly', 'Half Yearly'),
            ('yearly', 'Yearly'),
            ('custom', 'Custom'),
        ],
        default='monthly'
    )
    grace_period_days = serializers.IntegerField(
        min_value=0,
        default=0
    )
    auto_payment_enabled = serializers.BooleanField(default=False)
    description = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    def validate_first_due_date(self, value):
        """Validate first due date"""
        if value < timezone.now().date():
            raise serializers.ValidationError(
                "First due date cannot be in the past."
            )
        return value
