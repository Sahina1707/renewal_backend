"""
Serializers for Customer Insights API endpoints.
Simplified design with single insights model and JSON storage.
"""

from rest_framework import serializers
from django.utils import timezone
from .models import CustomerInsight
from apps.customers.models import Customer


class CustomerBasicInfoSerializer(serializers.Serializer):
    """Serializer for basic customer information - handles both Customer objects and dicts"""
    
    id = serializers.IntegerField()
    customer_code = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField()
    profile = serializers.CharField()
    customer_since = serializers.DateField(allow_null=True)
    total_policies = serializers.IntegerField()
    total_premium = serializers.DecimalField(max_digits=12, decimal_places=2)


class PaymentScheduleSerializer(serializers.Serializer):
    """Serializer for payment schedule data"""
    
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    due_date = serializers.DateField()
    policy = serializers.CharField()
    days_until_due = serializers.IntegerField()
    status = serializers.CharField()


class PaymentHistorySerializer(serializers.Serializer):
    """Serializer for payment history data"""
    
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateTimeField()
    status = serializers.CharField()
    mode = serializers.CharField()
    policy = serializers.CharField()


class YearlyPaymentSummarySerializer(serializers.Serializer):
    """Serializer for yearly payment summary"""
    
    year = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    payments_count = serializers.IntegerField()
    payments = PaymentHistorySerializer(many=True)


class PaymentHistoryResponseSerializer(serializers.Serializer):
    """Serializer for payment history response"""
    
    yearly_breakdown = YearlyPaymentSummarySerializer(many=True)
    summary = serializers.DictField()


class CommunicationHistorySerializer(serializers.Serializer):
    """Serializer for communication history"""
    
    id = serializers.IntegerField()
    date = serializers.DateTimeField()
    channel = serializers.CharField()
    outcome = serializers.CharField()
    message_content = serializers.CharField()
    response_received = serializers.CharField(required=False)


class CommunicationHistoryResponseSerializer(serializers.Serializer):
    """Serializer for communication history response"""
    
    total_communications = serializers.IntegerField()
    by_channel = serializers.DictField()
    recent_communications = CommunicationHistorySerializer(many=True)


class ClaimHistorySerializer(serializers.Serializer):
    """Serializer for claim history"""
    
    id = serializers.IntegerField()
    title = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    claim_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    incident_date = serializers.DateField()
    claim_number = serializers.CharField()
    adjuster = serializers.CharField()
    rejection_reason = serializers.CharField(required=False)


class ClaimsHistoryResponseSerializer(serializers.Serializer):
    """Serializer for claims history response"""
    
    claims = ClaimHistorySerializer(many=True)
    summary = serializers.DictField()


class CustomerInsightsResponseSerializer(serializers.Serializer):
    """Main serializer for customer insights response - simplified"""
    
    customer_info = CustomerBasicInfoSerializer()
    payment_insights = serializers.DictField()
    communication_insights = serializers.DictField()
    claims_insights = serializers.DictField()
    profile_insights = serializers.DictField()
    payment_schedule = serializers.DictField()
    payment_history = serializers.DictField()
    calculated_at = serializers.DateTimeField()
    is_cached = serializers.BooleanField()


class PaymentScheduleResponseSerializer(serializers.Serializer):
    """Serializer for payment schedule response"""
    
    upcoming_payments = PaymentScheduleSerializer(many=True)
    next_payment = PaymentScheduleSerializer(required=False)


class CustomerInsightSerializer(serializers.ModelSerializer):
    """Serializer for CustomerInsight model - simplified"""
    
    customer = CustomerBasicInfoSerializer(read_only=True)
    
    class Meta:
        model = CustomerInsight
        fields = [
            'id', 'customer', 'calculated_at', 'payment_insights',
            'communication_insights', 'claims_insights', 'profile_insights',
            'is_cached', 'cache_expires_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'calculated_at']


class CustomerInsightsSummarySerializer(serializers.Serializer):
    """Serializer for customer insights summary"""
    
    customer_id = serializers.IntegerField()
    customer_name = serializers.CharField()
    customer_code = serializers.CharField()
    total_premiums_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    on_time_payment_rate = serializers.FloatField()
    total_communications = serializers.IntegerField()
    satisfaction_rating = serializers.FloatField()
    total_claims = serializers.IntegerField()
    approval_rate = serializers.FloatField()
    risk_level = serializers.CharField()
    customer_segment = serializers.CharField()
    last_updated = serializers.DateTimeField()


class InsightsDashboardSerializer(serializers.Serializer):
    """Serializer for insights dashboard data"""
    
    total_customers = serializers.IntegerField()
    high_value_customers = serializers.IntegerField()
    customers_with_claims = serializers.IntegerField()
    avg_satisfaction_rating = serializers.FloatField()
    total_premiums_collected = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_reliability_avg = serializers.FloatField()
    recent_insights = CustomerInsightsSummarySerializer(many=True)


class CustomerInsightsFilterSerializer(serializers.Serializer):
    """Serializer for filtering customer insights"""
    
    customer_segment = serializers.CharField(required=False)
    risk_level = serializers.CharField(required=False)
    payment_reliability = serializers.CharField(required=False)
    engagement_level = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    limit = serializers.IntegerField(default=50, max_value=100)
    offset = serializers.IntegerField(default=0, min_value=0)


class CustomerInsightsBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating customer insights"""
    
    customer_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    force_recalculate = serializers.BooleanField(default=False)


class CustomerInsightsRecalculateSerializer(serializers.Serializer):
    """Serializer for recalculating customer insights"""
    
    force_recalculate = serializers.BooleanField(default=False)
    sections = serializers.ListField(
        child=serializers.ChoiceField(choices=['payment', 'communication', 'claims', 'profile']),
        required=False,
        help_text="Specific sections to recalculate (all if not specified)"
    )
