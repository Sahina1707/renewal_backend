from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from apps.customers.models import Customer

class CustomerFinancialProfile(BaseModel):
    
    INCOME_SOURCE_CHOICES = [
        ('salary', 'Salary'),
        ('business', 'Business'),
        ('investment', 'Investment'),
        ('pension', 'Pension'),
        ('freelance', 'Freelance'),
        ('rental', 'Rental Income'),
        ('other', 'Other'),
    ]
    
    RISK_PROFILE_CHOICES = [
        ('conservative', 'Conservative'),
        ('moderate', 'Moderate'),
        ('aggressive', 'Aggressive'),
        ('very_aggressive', 'Very Aggressive'),
    ]
    
    # Foreign Key to Customer
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='financial_profile',
        help_text="Customer associated with this financial profile"
    )
    
    # Income Information
    annual_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Customer's annual income"
    )
    
    income_captured_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when income information was captured"
    )
    
    income_source = models.CharField(
        max_length=50,
        choices=INCOME_SOURCE_CHOICES,
        blank=True,
        help_text="Primary source of customer's income"
    )
    
    # Policy Capacity and Recommendations
    policy_capacity_utilization = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of policy capacity currently utilized (0-100)"
    )
    
    recommended_policies_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of policies recommended for this customer"
    )
    
    recommended_policies_value = models.PositiveIntegerField(
        default=0,
        help_text="Total value of recommended policies"
    )
    
    # Risk Assessment
    risk_profile = models.CharField(
        max_length=20,
        choices=RISK_PROFILE_CHOICES,
        blank=True,
        help_text="Customer's risk tolerance profile"
    )
    
    tolerance_score = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Risk tolerance score (0.0 to 10.0)"
    )
    
    class Meta:
        db_table = 'customer_financial_profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['annual_income']),
            models.Index(fields=['risk_profile']),
            models.Index(fields=['income_captured_date']),
        ]
    
    def __str__(self):
        return f"Financial Profile - {self.customer.full_name}"
    
    @property
    def income_range(self):
        """Return income range category"""
        if not self.annual_income:
            return 'Unknown'
        
        income = float(self.annual_income)
        if income < 300000:
            return 'Low'
        elif income < 1000000:
            return 'Medium'
        elif income < 2500000:
            return 'High'
        else:
            return 'Very High'
    
    @property
    def capacity_status(self):
        """Return capacity utilization status"""
        if self.policy_capacity_utilization is None:
            return 'Unknown'
        
        if self.policy_capacity_utilization < 25:
            return 'Low Utilization'
        elif self.policy_capacity_utilization < 50:
            return 'Medium Utilization'
        elif self.policy_capacity_utilization < 75:
            return 'High Utilization'
        else:
            return 'Near Full Capacity'
    
    def calculate_recommended_premium(self):
        """Calculate recommended annual premium based on income"""
        if not self.annual_income:
            return 0
        
        base_percentage = 0.12  
        
        # Adjust based on risk profile
        risk_multipliers = {
            'conservative': 0.8,
            'moderate': 1.0,
            'aggressive': 1.2,
            'very_aggressive': 1.4,
        }
        
        multiplier = risk_multipliers.get(self.risk_profile, 1.0)
        recommended_premium = float(self.annual_income) * base_percentage * multiplier
        
        return round(recommended_premium, 2)
    
    def update_capacity_utilization(self):
        """Update policy capacity utilization based on current policies"""
        if not self.annual_income:
            return
        
        # Get total premium of active policies
        total_premium = self.customer.policies.filter(
            status='active',
            is_deleted=False
        ).aggregate(
            total=models.Sum('premium_amount')
        )['total'] or 0
        
        # Calculate utilization percentage
        recommended_premium = self.calculate_recommended_premium()
        if recommended_premium > 0:
            utilization = (float(total_premium) / recommended_premium) * 100
            self.policy_capacity_utilization = min(100, round(utilization))
            self.save(update_fields=['policy_capacity_utilization'])
