"""
Serializers for Customer Insights API endpoints.
Updated to support nested Customer Profile structure from the video.
"""

from rest_framework import serializers
from django.utils import timezone
from .models import CustomerInsight
from apps.customers.models import Customer

# --- 1. Helper Serializers (Defined First) ---

class CustomerBasicInfoSerializer(serializers.Serializer):
    """Serializer for basic customer information"""
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

class ProfilePaymentStatsSerializer(serializers.Serializer):
    """Matches the 'Payment History' row inside Customer Profiling"""
    on_time_percentage = serializers.IntegerField()
    customer_tenure = serializers.CharField()
    payment_rating = serializers.CharField()
    total_paid_ytd = serializers.DecimalField(max_digits=12, decimal_places=2)

class PolicyInformationSerializer(serializers.Serializer):
    """Matches the 'Policy Information' row inside Customer Profiling"""
    active_policies = serializers.IntegerField()
    family_policies = serializers.IntegerField()
    expired_policies = serializers.IntegerField()

class PaymentScheduleSerializer(serializers.Serializer):
    """Serializer for payment schedule data"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    due_date = serializers.DateField()
    policy = serializers.CharField()
    days_until_due = serializers.IntegerField()
    status = serializers.CharField()

class PaymentHistoryCardSerializer(serializers.Serializer):
    """Serializer for individual payment cards in history list"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateTimeField()
    status = serializers.CharField()
    mode = serializers.CharField()
    policy = serializers.CharField()

class YearlyPaymentSummarySerializer(serializers.Serializer):
    """Serializer for yearly payment grouping"""
    year = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    payments_count = serializers.IntegerField()
    payments = PaymentHistoryCardSerializer(many=True)

class CommunicationHistorySerializer(serializers.Serializer):
    """Serializer for communication history"""
    id = serializers.IntegerField()
    date = serializers.DateTimeField()
    channel = serializers.CharField()
    outcome = serializers.CharField()
    message_content = serializers.CharField()
    response_received = serializers.CharField(required=False)
    attachment_count = serializers.IntegerField(required=False)
    agent_name = serializers.CharField(required=False)
    timeline_event = serializers.CharField(required=False)
    contact_name = serializers.CharField(required=False)
    contact_details = serializers.CharField(required=False)
    communication_summary = serializers.CharField(required=False)
    inbound = serializers.BooleanField(required=False)
    resolved = serializers.BooleanField(required=False)
    priority = serializers.CharField(required=False)
    time = serializers.CharField(required=False)
    agent = serializers.CharField(required=False)
    duration = serializers.IntegerField(required=False, allow_null=True)

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
    timeline_events = serializers.ListField(required=False) 
    document_attachments = serializers.IntegerField(required=False) 
    priority = serializers.CharField(required=False)


# --- 2. Response Serializers ---

class PaymentHistoryResponseSerializer(serializers.Serializer):
    """Serializer for payment history response"""
    yearly_breakdown = YearlyPaymentSummarySerializer(many=True)
    summary = serializers.DictField()

class CommunicationHistoryResponseSerializer(serializers.Serializer):
    """Serializer for communication history response"""
    total_communications = serializers.IntegerField()
    by_channel = serializers.DictField()
    all_communications = CommunicationHistorySerializer(many=True) 

class ClaimsHistoryResponseSerializer(serializers.Serializer):
    """Serializer for claims history response"""
    claims = ClaimHistorySerializer(many=True)
    summary = serializers.DictField()

class PaymentScheduleResponseSerializer(serializers.Serializer):
    """Serializer for payment schedule response"""
    upcoming_payments = PaymentScheduleSerializer(many=True)
    next_payment = PaymentScheduleSerializer(required=False)


# --- 3. Main Insights Serializers ---

class CustomerInsightsResponseSerializer(serializers.Serializer):
    """Main serializer for customer insights response"""
    customer_info = CustomerBasicInfoSerializer()
    
    # Specific sections
    payment_insights = serializers.DictField()
    communication_insights = serializers.DictField()
    claims_insights = serializers.DictField()
    
    # Profile can be a flexible Dict or use nested serializers if you strictly enforce structure
    profile_insights = serializers.DictField() 
    
    # Detailed Data Lists
    payment_schedule = serializers.DictField()
    payment_history = serializers.DictField()
    
    # Meta
    calculated_at = serializers.DateTimeField()
    is_cached = serializers.BooleanField()

class CustomerInsightSerializer(serializers.ModelSerializer):
    """Serializer for CustomerInsight model"""
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
    """Serializer for dashboard summary"""
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
    total_customers = serializers.IntegerField()
    high_value_customers = serializers.IntegerField()
    customers_with_claims = serializers.IntegerField()
    avg_satisfaction_rating = serializers.FloatField()
    total_premiums_collected = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_reliability_avg = serializers.FloatField()
    recent_insights = CustomerInsightsSummarySerializer(many=True)

class CustomerInsightsFilterSerializer(serializers.Serializer):
    customer_segment = serializers.CharField(required=False)
    risk_level = serializers.CharField(required=False)
    payment_reliability = serializers.CharField(required=False)
    engagement_level = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    limit = serializers.IntegerField(default=50, max_value=100)
    offset = serializers.IntegerField(default=0, min_value=0)

class CustomerInsightsBulkUpdateSerializer(serializers.Serializer):
    customer_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    force_recalculate = serializers.BooleanField(default=False)

class CustomerInsightsRecalculateSerializer(serializers.Serializer):
    force_recalculate = serializers.BooleanField(default=False)
    sections = serializers.ListField(
        child=serializers.ChoiceField(choices=['payment', 'communication', 'claims', 'profile']),
        required=False,
        help_text="Specific sections to recalculate (all if not specified)"
    )