"""
Customer Policy Preferences models for the Intelipro Insurance Policy Renewal System.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from apps.customers.models import Customer
from apps.renewals.models import RenewalCase


class CustomerPolicyPreference(BaseModel):
    """
    Customer policy preferences for renewal and insurance selection.
    """
    
    COVERAGE_TYPE_CHOICES = [
        ('basic', 'Basic Coverage'),
        ('standard', 'Standard Coverage'),
        ('comprehensive', 'Comprehensive Coverage'),
        ('premium', 'Premium Coverage'),
        ('custom', 'Custom Coverage'),
    ]
    
    PAYMENT_MODE_CHOICES = [
        ('annual', 'Annual'),
        ('semi_annual', 'Semi-Annual'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
        ('one_time', 'One Time'),
        ('installments', 'Installments'),
    ]
    
    # Foreign Keys
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='policy_preferences',
        help_text="Customer this preference belongs to"
    )
    
    renewal_cases = models.ForeignKey(
        RenewalCase,
        on_delete=models.CASCADE,
        related_name='policy_preferences',
        help_text="Renewal case this preference is for"
    )
    
    # Preference Fields
    preferred_tenure = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Preferred policy tenure in years"
    )
    
    coverage_type = models.CharField(
        max_length=50,
        choices=COVERAGE_TYPE_CHOICES,
        default='standard',
        help_text="Preferred coverage type"
    )
    
    preferred_insurer = models.CharField(
        max_length=100,
        blank=True,
        help_text="Preferred insurance company"
    )
    
    add_ons = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional coverage add-ons and preferences"
    )
    
    payment_mode = models.CharField(
        max_length=50,
        choices=PAYMENT_MODE_CHOICES,
        default='annual',
        help_text="Preferred payment mode"
    )
    
    # Additional preference fields
    auto_renewal = models.BooleanField(
        default=False,
        help_text="Whether customer prefers auto-renewal"
    )
    
    digital_policy = models.BooleanField(
        default=True,
        help_text="Whether customer prefers digital policy documents"
    )
    
    communication_preference = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('sms', 'SMS'),
            ('phone', 'Phone'),
            ('whatsapp', 'WhatsApp'),
            ('postal', 'Postal Mail'),
        ],
        default='email',
        help_text="Preferred communication method"
    )
    
    budget_range_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Minimum budget for premium"
    )
    
    budget_range_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Maximum budget for premium"
    )
    
    special_requirements = models.TextField(
        blank=True,
        help_text="Any special requirements or notes"
    )
    
    # Tracking field as per diagram
    created_vy = models.IntegerField(
        blank=True,
        null=True,
        help_text="Created by year for tracking purposes"
    )
    
    # For the policyTimelne page
    avoided_policy_types = models.CharField(
        max_length=255,
        blank=True,
        help_text="Policy types the customer prefers to avoid (e.g., 'ULIP, Endowment')"
    )
    
    class Meta:
        db_table = 'customer_policy_preferences'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['renewal_cases']),
            models.Index(fields=['coverage_type']),
            models.Index(fields=['preferred_insurer']),
            models.Index(fields=['payment_mode']),
            models.Index(fields=['auto_renewal']),
            models.Index(fields=['created_vy']),
        ]
        unique_together = ['customer', 'renewal_cases']
    
    def __str__(self):
        return f"{self.customer.full_name} - {self.coverage_type} - {self.preferred_tenure}Y"
    
    def save(self, *args, **kwargs):
        """Override save to set created_vy automatically"""
        if not self.created_vy and not self.pk:
            from datetime import datetime
            self.created_vy = datetime.now().year
        super().save(*args, **kwargs)
    
    @property
    def preference_summary(self):
        """Return a summary of customer preferences"""
        parts = []
        parts.append(f"{self.get_coverage_type_display()}")
        parts.append(f"{self.preferred_tenure} years")
        parts.append(f"{self.get_payment_mode_display()}")
        if self.preferred_insurer:
            parts.append(f"Insurer: {self.preferred_insurer}")
        return " | ".join(parts)
    
    @property
    def budget_summary(self):
        """Return budget range summary"""
        if self.budget_range_min and self.budget_range_max:
            return f"₹{self.budget_range_min:,.2f} - ₹{self.budget_range_max:,.2f}"
        elif self.budget_range_min:
            return f"Min: ₹{self.budget_range_min:,.2f}"
        elif self.budget_range_max:
            return f"Max: ₹{self.budget_range_max:,.2f}"
        return "No budget specified"
    
    @property
    def add_ons_summary(self):
        """Return a summary of selected add-ons"""
        if not self.add_ons:
            return "No add-ons selected"
        
        add_on_list = []
        for key, value in self.add_ons.items():
            if isinstance(value, bool) and value:
                add_on_list.append(key.replace('_', ' ').title())
            elif isinstance(value, str) and value:
                add_on_list.append(f"{key.replace('_', ' ').title()}: {value}")
        
        return ", ".join(add_on_list) if add_on_list else "No add-ons selected"
    
    @property
    def is_premium_customer(self):
        """Check if customer has premium preferences"""
        premium_indicators = [
            self.coverage_type in ['comprehensive', 'premium'],
            self.budget_range_max and self.budget_range_max > 50000,
            self.preferred_tenure >= 5,
            bool(self.add_ons and len(self.add_ons) > 3)
        ]
        return sum(premium_indicators) >= 2
    
    @property
    def preference_score(self):
        """Calculate a preference completeness score (0-100)"""
        score = 0
        
        # Basic preferences (40 points)
        if self.preferred_tenure:
            score += 10
        if self.coverage_type:
            score += 10
        if self.payment_mode:
            score += 10
        if self.preferred_insurer:
            score += 10
        
        # Budget information (20 points)
        if self.budget_range_min or self.budget_range_max:
            score += 20
        
        # Additional preferences (20 points)
        if self.add_ons:
            score += 10
        if self.communication_preference:
            score += 5
        if self.special_requirements:
            score += 5
        
        # Engagement indicators (20 points)
        if self.auto_renewal:
            score += 10
        if self.digital_policy:
            score += 10
        
        return min(score, 100)
