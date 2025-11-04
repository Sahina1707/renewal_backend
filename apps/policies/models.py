from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel, TimestampedModel
from apps.customers.models import Customer
import uuid
from decimal import Decimal
from django.utils import timezone # <-- 1. ADDED THIS IMPORT

User = get_user_model()

class PolicyAgent(BaseModel):
    """Policy agents model for storing agent information"""
    
    agent_code = models.CharField(max_length=50, unique=True, help_text="Auto-generated agent code")
    agent_name = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'policy_agents'
        ordering = ['agent_name']
        indexes = [
            models.Index(fields=['agent_code']),
            models.Index(fields=['agent_name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.agent_code} - {self.agent_name}"
    
    def save(self, *args, **kwargs):
        if not self.agent_code:
            # Auto-generate agent code if not provided
            self.agent_code = self.generate_agent_code()
        super().save(*args, **kwargs)
    
    def generate_agent_code(self):
        """Generate a unique agent code"""
        import random
        import string
        
        # Generate a code like AGT-1234
        while True:
            code = f"AGT-{random.randint(1000, 9999)}"
            if not PolicyAgent.objects.filter(agent_code=code).exists():
                return code

class PolicyType(BaseModel):
    """Types of insurance policies (Life, Health, Motor, etc.)"""

    CATEGORY_CHOICES = [
        ('Motor', 'Motor'),
        ('Life', 'Life'),
        ('Property', 'Property'),
        ('Health', 'Health'),
        ('Travel', 'Travel'),
    ]

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Motor', db_index=True, help_text="Insurance category based on policy type")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    base_premium_rate = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    coverage_details = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'policy_types'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Policy(BaseModel):
    """Main policy model"""
    POLICY_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('expiring_soon', 'Expiring Soon'),
        ('pre_due', 'Pre Due'),
        ('reinstatement', 'Reinstatement'),
        ('policy_due', 'Policy Due'),
    ]
    
    policy_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='policies')
    policy_type = models.ForeignKey(PolicyType, on_delete=models.CASCADE, related_name='policies')
    
    # Policy Details
    start_date = models.DateField()
    end_date = models.DateField()
    renewal_date = models.DateField(null=True, blank=True, help_text="Auto-calculated renewal date")
    renewal_reminder_days = models.IntegerField(default=30, help_text="Days before end_date to start renewal process (15, 30, 45, 60)")
    grace_period_days = models.IntegerField(default=30, help_text="Grace period days after policy expiry")
    premium_amount = models.DecimalField(max_digits=12, decimal_places=2)
    sum_assured = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=POLICY_STATUS_CHOICES, default='pending')
    
    # Payment Details
    payment_frequency = models.CharField(max_length=20, choices=[
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half Yearly'),
        ('yearly', 'Yearly'),
    ], default='yearly')
    
    # Additional Details
    nominee_name = models.CharField(max_length=200, blank=True)
    nominee_relationship = models.CharField(max_length=100, blank=True)
    nominee_contact = models.CharField(max_length=20, blank=True)

    # Coverage Details - Policy-specific coverage information
    coverage_details = models.JSONField(
        default=dict,
        help_text="Policy-specific coverage details that override or extend policy type defaults"
    )

    # Metadata
    policy_document = models.FileField(upload_to='policies/documents/', blank=True, null=True)
    terms_conditions = models.TextField(blank=True)
    special_conditions = models.TextField(blank=True)
    agent = models.ForeignKey(PolicyAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name='policies', help_text="Policy agent")
    
    # System Fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_policies')
    last_modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='modified_policies')
    
    class Meta:
        db_table = 'policies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['policy_number']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['end_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.policy_number} - {self.customer.full_name}"
    
    def calculate_renewal_date(self):
        """Calculate renewal date based on end_date and renewal_reminder_days"""
        from datetime import timedelta
        if self.end_date:
            return self.end_date - timedelta(days=self.renewal_reminder_days)
        return None

    def get_complete_coverage_details(self):
        """
        Get complete coverage details by merging policy type defaults with policy-specific overrides
        Policy-specific coverage details take precedence over policy type defaults
        """
        # Start with policy type coverage details as base
        complete_coverage = self.policy_type.coverage_details.copy() if self.policy_type.coverage_details else {}

        # Override/extend with policy-specific coverage details
        if self.coverage_details:
            # Deep merge the dictionaries
            def deep_merge(base_dict, override_dict):
                for key, value in override_dict.items():
                    if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                        deep_merge(base_dict[key], value)
                    else:
                        base_dict[key] = value
                return base_dict

            complete_coverage = deep_merge(complete_coverage, self.coverage_details)

        return complete_coverage

    def save(self, *args, **kwargs):
        """Override save to auto-calculate renewal_date"""
        # Auto-calculate renewal date if not manually set
        if self.end_date and not self.renewal_date:
            self.renewal_date = self.calculate_renewal_date()
        super().save(*args, **kwargs)

    @property
    def is_due_for_renewal(self):
        """Check if policy is due for renewal (within renewal_reminder_days)"""
        from datetime import date
        if self.renewal_date:
            return date.today() >= self.renewal_date
        return False

    @property
    def days_until_renewal(self):
        """Get number of days until renewal date"""
        from datetime import date
        if self.renewal_date:
            delta = self.renewal_date - date.today()
            return delta.days
        return None

    @property
    def days_until_expiry(self):
        """Get number of days until policy expires"""
        from datetime import date
        if self.end_date:
            delta = self.end_date - date.today()
            return delta.days
        return None
    
    @property
    def days_to_expiry(self):
        """Days remaining until policy expires"""
        from datetime import date
        return (self.end_date - date.today()).days

    @classmethod
    def set_renewal_reminder_days(cls, policy_ids, reminder_days):
        """Bulk update renewal reminder days for multiple policies"""
        from datetime import timedelta

        policies = cls.objects.filter(id__in=policy_ids)
        updated_count = 0

        for policy in policies:
            policy.renewal_reminder_days = reminder_days
            if policy.end_date:
                policy.renewal_date = policy.end_date - timedelta(days=reminder_days)
            policy.save()
            updated_count += 1

        return updated_count

    @classmethod
    def get_policies_by_renewal_urgency(cls):
        """Get policies grouped by renewal urgency"""
        from datetime import date, timedelta

        today = date.today()

        return {
            'overdue': cls.objects.filter(
                renewal_date__lt=today,
                status__in=['active', 'pending', 'expiring_soon']
            ),
            'due_today': cls.objects.filter(
                renewal_date=today,
                status__in=['active', 'pending', 'expiring_soon']
            ),
            'due_this_week': cls.objects.filter(
                renewal_date__lte=today + timedelta(days=7),
                renewal_date__gt=today,
                status__in=['active', 'pending', 'expiring_soon']
            ),
            'due_this_month': cls.objects.filter(
                renewal_date__lte=today + timedelta(days=30),
                renewal_date__gt=today + timedelta(days=7),
                status__in=['active', 'pending', 'expiring_soon']
            ),
        }

class PolicyRenewal(BaseModel):
    """Policy renewal tracking"""
    RENEWAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='renewals')
    renewal_date = models.DateField()
    new_premium_amount = models.DecimalField(max_digits=12, decimal_places=2)
    new_sum_assured = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=RENEWAL_STATUS_CHOICES, default='pending')
    
    # Renewal Details
    renewal_notice_sent = models.BooleanField(default=False)
    renewal_notice_date = models.DateTimeField(null=True, blank=True)
    customer_response = models.CharField(max_length=20, choices=[
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('needs_time', 'Needs Time'),
        ('no_response', 'No Response'),
    ], default='no_response')
    
    # Communication Tracking
    contact_attempts = models.PositiveIntegerField(default=0)
    last_contact_date = models.DateTimeField(null=True, blank=True)
    contact_method = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('in_person', 'In Person'),
    ], blank=True)
    
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_renewals')
    
    class Meta:
        db_table = 'policy_renewals'
        ordering = ['-renewal_date']
        indexes = [
            models.Index(fields=['renewal_date', 'status']),
            models.Index(fields=['policy', 'status']),
        ]
    
    def __str__(self):
        return f"Renewal - {self.policy.policy_number} ({self.renewal_date})"

class PolicyClaim(BaseModel):
    """Insurance claims"""
    CLAIM_STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
        ('closed', 'Closed'),
    ]
    
    CLAIM_TYPE_CHOICES = [
        ('death', 'Death Claim'),
        ('maturity', 'Maturity Claim'),
        ('surrender', 'Surrender'),
        ('partial_withdrawal', 'Partial Withdrawal'),
        ('accident', 'Accident'),
        ('medical', 'Medical'),
        ('disability', 'Disability'),
        ('other', 'Other'),
    ]
    
    claim_number = models.CharField(max_length=50, unique=True)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='claims')
    claim_type = models.CharField(max_length=30, choices=CLAIM_TYPE_CHOICES)
    claim_amount = models.DecimalField(max_digits=15, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Claim Details
    incident_date = models.DateField()
    claim_date = models.DateField()
    status = models.CharField(max_length=20, choices=CLAIM_STATUS_CHOICES, default='submitted')
    description = models.TextField()
    
    # Processing Details
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_claims')
    review_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Payment Details
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'policy_claims'
        ordering = ['-claim_date']
        indexes = [
            models.Index(fields=['claim_number']),
            models.Index(fields=['policy', 'status']),
            models.Index(fields=['claim_date', 'status']),
        ]
    
    def __str__(self):
        return f"Claim {self.claim_number} - {self.policy.policy_number}"

class PolicyDocument(BaseModel):
    """Policy related documents"""
    DOCUMENT_TYPE_CHOICES = [
        ('policy_document', 'Policy Document'),
        ('renewal_notice', 'Renewal Notice'),
        ('claim_form', 'Claim Form'),
        ('medical_report', 'Medical Report'),
        ('identity_proof', 'Identity Proof'),
        ('address_proof', 'Address Proof'),
        ('income_proof', 'Income Proof'),
        ('other', 'Other'),
    ]
    
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    document_name = models.CharField(max_length=200)
    file = models.FileField(upload_to='policies/documents/')
    file_size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=100)
    
    # Metadata
    description = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_documents')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    
    class Meta:
        db_table = 'policy_documents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.document_name} - {self.policy.policy_number}"

class PolicyBeneficiary(BaseModel):
    """Policy beneficiaries/nominees"""
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='beneficiaries')
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    
    # Beneficiary Details
    date_of_birth = models.DateField(null=True, blank=True)
    id_type = models.CharField(max_length=50, blank=True)
    id_number = models.CharField(max_length=100, blank=True)
    percentage_share = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'policy_beneficiaries'
        ordering = ['-is_primary', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.policy.policy_number}"

class PolicyPayment(BaseModel):
    """Policy payment tracking"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('net_banking', 'Net Banking'),
        ('upi', 'UPI'),
        ('wallet', 'Wallet'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Payment Details
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Period Details
    payment_for_period_start = models.DateField()
    payment_for_period_end = models.DateField()
    
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'policy_payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['policy', 'payment_date']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.amount} - {self.policy.policy_number}"

class PolicyNote(BaseModel):
    """Internal notes for policies"""
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    is_customer_visible = models.BooleanField(default=False)
    note_type = models.CharField(max_length=20, choices=[
        ('general', 'General'),
        ('follow_up', 'Follow Up'),
        ('complaint', 'Complaint'),
        ('renewal', 'Renewal'),
        ('claim', 'Claim'),
        ('payment', 'Payment'),
    ], default='general')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'policy_notes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note - {self.policy.policy_number}"


class PolicyMember(BaseModel):
    """Policy members (family members covered under a policy)"""
    
    RELATION_CHOICES = [
        ('self', 'Self'),
        ('spouse', 'Spouse'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('other', 'Other'),
    ]
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    # Foreign Keys
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='policy_members',
        help_text="Primary customer who owns the policy"
    )
    policy = models.ForeignKey(
        Policy, 
        on_delete=models.CASCADE, 
        related_name='policy_members',
        help_text="Policy this member is covered under"
    )
    renewal_case = models.ForeignKey(
        'renewals.RenewalCase',
        on_delete=models.CASCADE,
        related_name='policy_members',
        null=True,
        blank=True,
        help_text="Renewal case this member belongs to"
    )
    
    # Member Details
    name = models.CharField(max_length=200, help_text="Full name of the policy member")
    relation = models.CharField(
        max_length=20, 
        choices=RELATION_CHOICES,
        help_text="Relationship to the primary customer"
    )
    dob = models.DateField(help_text="Date of birth")
    gender = models.CharField(
        max_length=10, 
        choices=GENDER_CHOICES,
        help_text="Gender"
    )
    
    # Financial Details
    sum_insured = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        help_text="Sum insured amount for this member"
    )
    premium_share = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Premium amount for this member"
    )
    
    class Meta:
        db_table = 'policy_members'
        ordering = ['relation', 'name']
        indexes = [
            models.Index(fields=['customer', 'policy']),
            models.Index(fields=['policy', 'relation']),
            models.Index(fields=['relation']),
            models.Index(fields=['renewal_case']),
        ]
        unique_together = ['policy', 'name', 'relation']
    
    def __str__(self):
        return f"{self.name} ({self.get_relation_display()}) - {self.policy.policy_number}"
    
    @property
    def age(self):
        """Calculate age dynamically from date of birth"""
        from datetime import date
        today = date.today()
        age = today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return age
    
    @property
    def initials(self):
        """Get initials from name"""
        names = self.name.split()
        if len(names) >= 2:
            return f"{names[0][0]}{names[-1][0]}".upper()
        elif len(names) == 1:
            return names[0][:2].upper()
        return "??"
# claims Timeline    
class ClaimTimelineEvent(BaseModel):
    """
    Stores a single event in the timeline of a policy claim.
    """
    claim = models.ForeignKey(
        PolicyClaim, 
        related_name="timeline_events", 
        on_delete=models.CASCADE
    )
    event_date = models.DateTimeField(default=timezone.now)
    event_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default='completed')

    class Meta:
        ordering = ['event_date'] 

    def __str__(self):
        return f"{self.event_name} for Claim {self.claim.claim_number}"
