"""
Claims models for the Intelipro Insurance Policy Renewal System.
"""

from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.customers.models import Customer
from apps.policies.models import Policy

User = get_user_model()


class Claim(BaseModel):
    """Model for insurance claims"""
    
    CLAIM_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('document_pending', 'Document Pending'),
        ('approved', 'Approved'),
        ('settled', 'Settled'),
        ('rejected', 'Rejected'),
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
    
    # Auto-generated claim number (CLM0001 format)
    claim_number = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Auto-generated claim number in format CLM0001"
    )
    
    # Foreign Keys
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='claims',
        db_column='customer_id',
        help_text="Customer associated with this claim"
    )
    
    policy = models.ForeignKey(
        Policy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claim_records',
        db_column='policy_id',
        help_text="Policy associated with this claim"
    )
    
    # Claim Details
    claim_type = models.CharField(
        max_length=50,
        choices=CLAIM_TYPE_CHOICES,
        help_text="Type of claim"
    )
    
    claim_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Claim amount"
    )
    
    description = models.TextField(
        help_text="Description of the claim"
    )
    
    status = models.CharField(
        max_length=20,
        choices=CLAIM_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current status of the claim"
    )
    
    # Additional fields
    insurance_company_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of the insurance company"
    )
    
    policy_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Policy number"
    )
    
    expire_date = models.DateField(
        null=True,
        blank=True,
        help_text="Policy expiration date"
    )
    
    incident_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the incident occurred"
    )
    
    reported_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the claim was reported"
    )
    
    remarks = models.TextField(
        blank=True,
        help_text="Additional remarks or notes"
    )
    
    class Meta:
        db_table = 'claims'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['claim_number']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['policy', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        if self.customer:
            customer_name = f"{self.customer.first_name} {self.customer.last_name}".strip()
            return f"{self.claim_number} - {customer_name}"
        return f"{self.claim_number} - N/A"
    
    def save(self, *args, **kwargs):
        # Auto-generate claim_number if not provided
        if not self.claim_number:
            self.claim_number = self.generate_claim_number()
        
        # Auto-populate policy_number from policy if available
        if self.policy and not self.policy_number:
            try:
                self.policy_number = self.policy.policy_number
            except AttributeError:
                pass
        
        # Auto-populate expire_date from policy if available
        if self.policy and not self.expire_date:
            try:
                if hasattr(self.policy, 'expiry_date') and self.policy.expiry_date:
                    self.expire_date = self.policy.expiry_date
                elif hasattr(self.policy, 'end_date') and self.policy.end_date:
                    self.expire_date = self.policy.end_date
            except AttributeError:
                pass
        
        super().save(*args, **kwargs)
    
    def generate_claim_number(self):
        """Generate a unique claim number in format CLM0001"""
        prefix = "CLM"
        
        # Get all existing claim numbers with the prefix
        existing_claims = Claim.objects.filter(
            claim_number__startswith=prefix
        ).values_list('claim_number', flat=True)
        
        max_number = 0
        for claim_number in existing_claims:
            try:
                # Extract number part (e.g., "CLM0001" -> "0001" -> 1)
                number_part = claim_number[len(prefix):]
                number = int(number_part)
                if number > max_number:
                    max_number = number
            except (ValueError, IndexError):
                continue
        
        next_number = max_number + 1
        return f"{prefix}{next_number:04d}"
    
    @property
    def customer_name(self):
        """Get customer full name"""
        if self.customer:
            return f"{self.customer.first_name} {self.customer.last_name}".strip()
        return None
    
    @property
    def mobile_number(self):
        """Get customer mobile number"""
        if self.customer:
            return self.customer.phone
        return None
    
    @property
    def email_id(self):
        """Get customer email"""
        if self.customer:
            return self.customer.email
        return None
    
class ClaimTimelineEvent(models.Model):
    """Stores individual events that make up the claims processing timeline."""
    claim = models.ForeignKey(
        Claim, 
        on_delete=models.CASCADE,
        related_name='timeline_events', 
        help_text="The claim this timeline event belongs to."
    )
    date = models.DateTimeField(
        help_text="The date and time the event occurred."
    )
    title = models.CharField(
        max_length=150,
        help_text="Short title of the event (e.g., 'Surveyor Assigned')."
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the event or action taken."
    )
    
    class Meta:
        ordering = ['date'] 
    def __str__(self):
        return f"{self.claim.claim_number} - {self.title}"