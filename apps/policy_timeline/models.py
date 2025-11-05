"""
Policy Timeline models for the Intelipro Insurance Policy Renewal System.
"""

from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.customers.models import Customer
from apps.policies.models import Policy

User = get_user_model()


class PolicyTimeline(BaseModel):
    """
    Policy Timeline model to track all policy events, communications, and changes
    """
    
    EVENT_TYPE_CHOICES = [
        ('communication', 'Communication'),
        ('creation', 'Policy Creation'),
        ('renewal', 'Policy Renewal'),
        ('modification', 'Policy Modification'),
        ('claim', 'Claim Event'),
        ('payment', 'Payment Event'),
        ('coverage_review', 'Coverage Review'),
        ('agent_interaction', 'Agent Interaction'),
    ]
    
    EVENT_STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
        ('in_progress', 'In Progress'),
    ]
    
    # Core Foreign Keys
    policy = models.ForeignKey(
        Policy, 
        on_delete=models.CASCADE, 
        related_name='timeline_events',
        help_text="Related policy"
    )
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='policy_timeline_events',
        help_text="Related customer"
    )
    agent = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='policy_timeline_events',
        help_text="Assigned agent for this event"
    )
    
    # Event Information
    event_type = models.CharField(
        max_length=20, 
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of timeline event"
    )
    event_title = models.CharField(
        max_length=200,
        help_text="Title of the event (e.g., 'Policy Renewed', 'Coverage Review')"
    )
    event_description = models.TextField(
        help_text="Detailed description of the event"
    )
    event_date = models.DateTimeField(
        db_index=True,
        help_text="When the event occurred"
    )
    event_status = models.CharField(
        max_length=20, 
        choices=EVENT_STATUS_CHOICES, 
        default='completed',
        help_text="Current status of the event"
    )
    
    # Financial Fields
    premium_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Premium amount at time of event"
    )
    coverage_details = models.TextField(
        blank=True,
        help_text="Coverage details at time of event"
    )
    discount_info = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Discount information (e.g., '5% multi-policy discount applied')"
    )
    
    # Outcome Fields
    outcome = models.TextField(
        blank=True,
        help_text="Outcome or result of the event"
    )
    follow_up_required = models.BooleanField(
        default=False,
        help_text="Whether follow-up is required"
    )
    follow_up_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date for follow-up action"
    )
    
    # Display Fields
    display_icon = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Icon identifier for timeline UI display"
    )
    is_milestone = models.BooleanField(
        default=False,
        help_text="Mark as important milestone event"
    )
    sequence_order = models.IntegerField(
        default=0,
        help_text="Order for displaying events in timeline"
    )
    
    class Meta:
        db_table = 'policy_timeline'
        ordering = ['-event_date', '-sequence_order']
        indexes = [
            models.Index(fields=['policy', 'event_date']),
            models.Index(fields=['customer', 'event_date']),
            models.Index(fields=['event_type', 'event_date']),
            models.Index(fields=['agent', 'event_date']),
            models.Index(fields=['event_status']),
            models.Index(fields=['is_milestone']),
        ]
    
    def __str__(self):
        return f"{self.event_title} - {self.policy.policy_number} ({self.event_date.strftime('%Y-%m-%d')})"
    
    @property
    def formatted_event_date(self):
        """Return formatted date for display"""
        return self.event_date.strftime('%b %d, %Y')
    
    @property
    def event_category_display(self):
        """Return display name for event type"""
        return dict(self.EVENT_TYPE_CHOICES).get(self.event_type, self.event_type)


class PolicyTimelineEvent(BaseModel):
    """
    Individual events within a policy timeline for detailed tracking
    """
    
    EVENT_CATEGORY_CHOICES = [
        ('creation', 'Creation'),
        ('renewal', 'Renewal'),
        ('modification', 'Modification'),
        ('claim', 'Claim'),
        ('payment', 'Payment'),
        ('communication', 'Communication'),
    ]
    
    timeline = models.ForeignKey(
        PolicyTimeline,
        on_delete=models.CASCADE,
        related_name='events',
        help_text="Parent timeline this event belongs to"
    )
    
    event_category = models.CharField(
        max_length=20,
        choices=EVENT_CATEGORY_CHOICES,
        help_text="Category of the event"
    )
    
    event_title = models.CharField(
        max_length=200,
        help_text="Title of the event"
    )
    
    event_description = models.TextField(
        help_text="Detailed description of the event"
    )
    
    event_date = models.DateTimeField(
        help_text="When the event occurred"
    )
    
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event-specific data"
    )
    
    class Meta:
        db_table = 'policy_timeline_events'
        ordering = ['-event_date']
        indexes = [
            models.Index(fields=['timeline', 'event_date']),
            models.Index(fields=['event_category']),
        ]
    
    def __str__(self):
        return f"{self.event_title} - {self.timeline.policy.policy_number}"


class CustomerTimelineSummary(BaseModel):
    """
    Summary statistics for customer timeline view
    """
    
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='timeline_summary',
        help_text="Customer this summary belongs to"
    )
    
    total_events = models.PositiveIntegerField(
        default=0,
        help_text="Total number of timeline events"
    )
    
    active_policies = models.PositiveIntegerField(
        default=0,
        help_text="Number of active policies"
    )
    
    total_premium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total annual premium across all policies"
    )
    
    last_activity_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date of last timeline activity"
    )
    
    class Meta:
        db_table = 'customer_timeline_summary'
    
    def __str__(self):
        return f"Timeline Summary - {self.customer.full_name}"


class PolicyTimelineFilter(BaseModel):
    """
    Saved filters for policy timeline views
    """
    
    FILTER_TYPE_CHOICES = [
        ('event_type', 'Event Type'),
        ('date_range', 'Date Range'),
        ('policy_status', 'Policy Status'),
        ('customer_segment', 'Customer Segment'),
    ]
    
    name = models.CharField(
        max_length=100,
        help_text="Name of the filter"
    )
    
    filter_type = models.CharField(
        max_length=20,
        choices=FILTER_TYPE_CHOICES,
        help_text="Type of filter"
    )
    
    filter_criteria = models.JSONField(
        default=dict,
        help_text="Filter criteria as JSON"
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is a default filter"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='timeline_filters',
        help_text="User who created this filter"
    )
    
    class Meta:
        db_table = 'policy_timeline_filters'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_filter_type_display()})"
    
class CustomerPaymentSchedule(BaseModel):
    """
    Model to track upcoming payments and payment history statistics for a customer.
    """
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('auto_debit', 'Auto-Debit'),
        ('manual', 'Manual Payment'),
    ]
    
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='payment_schedule',
        help_text="Customer this schedule belongs to"
    )
    
    # Payment Statistics (from Payment Patterns & History)
    total_payments_last_12_months = models.PositiveSmallIntegerField(
        default=0,
        help_text="Total expected payments in the last 12 months"
    )
    on_time_payments_last_12_months = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of on-time payments in the last 12 months"
    )
    total_paid_last_12_months = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total premium amount paid in the last 12 months"
    )
    average_payment_timing_days = models.SmallIntegerField(
        default=0,
        help_text="Average payment timing (e.g., 5 days early)"
    )
    preferred_payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='auto_debit',
        help_text="Customer's preferred payment method for premium"
    )
    late_payment_instances = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of late payment instances"
    )

    class Meta:
        db_table = 'customer_payment_schedule'
    
    def __str__(self):
        return f"Payment Schedule for {self.customer.full_name}"


class UpcomingPayment(BaseModel):
    """
    Model for individual upcoming premium payments.
    """
    
    policy = models.ForeignKey(
        Policy, 
        on_delete=models.CASCADE, 
        related_name='upcoming_payments',
        help_text="Related policy"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='upcoming_payments',
        help_text="Related customer"
    )
    due_date = models.DateField(
        help_text="Date the payment is due"
    )
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Amount of the premium payment due"
    )
    days_to_due = models.SmallIntegerField(
        help_text="Calculated days remaining until due date"
    )
    
    class Meta:
        db_table = 'upcoming_payments'
        ordering = ['due_date']
    
    def __str__(self):
        return f"Payment of {self.amount_due} for {self.policy.policy_number} on {self.due_date}"

