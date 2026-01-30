from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.customers.models import Customer
from apps.policies.models import Policy, PolicyType

User = get_user_model()

class AIPolicyRecommendation(BaseModel):
    
    PRIORITY_LEVEL_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('under_review', 'Under Review'),
    ]
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='ai_policy_recommendations',
        help_text="Customer this recommendation is for"
    )
    current_policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name='ai_recommendations_based_on',
        null=True,
        blank=True,
        help_text="Customer's current policy this recommendation is based on"
    )
    recommended_policy_type = models.ForeignKey(
        PolicyType,
        on_delete=models.CASCADE,
        related_name='ai_recommendations',
        help_text="Recommended policy type"
    )
    recommendation_title = models.CharField(
        max_length=200,
        help_text="Title of the recommendation (e.g., 'Critical Illness Insurance')"
    )
    recommendation_reason = models.TextField(
        help_text="Detailed explanation of why this policy is recommended"
    )
    coverage_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Recommended coverage amount"
    )
    estimated_premium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Estimated yearly premium amount"
    )
    priority_level = models.CharField(
        max_length=10,
        choices=PRIORITY_LEVEL_CHOICES,
        default='medium',
        db_index=True,
        help_text="Priority level of this recommendation"
    )
    recommendation_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="AI recommendation strength (0.0000 to 1.0000)"
    )
    benefits = models.JSONField(
        default=list,
        help_text="List of key benefits of this policy recommendation"
    )
    target_audience = models.TextField(
        blank=True,
        help_text="Description of who this recommendation suits best"
    )
    validity_period = models.IntegerField(
        default=30,
        help_text="Number of days this recommendation is valid"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text="Current status of this recommendation"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this recommendation should be displayed"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this recommendation was generated"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this recommendation expires"
    )
    viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When customer first viewed this recommendation"
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When customer responded to this recommendation"
    )
    
    class Meta:
        db_table = 'ai_policy_recommendations'
        ordering = ['-generated_at', '-priority_level']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['recommended_policy_type']),
            models.Index(fields=['priority_level', 'status']),
            models.Index(fields=['generated_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.recommendation_title} for {self.customer.name}"
    
    def is_expired(self):
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False
    
    def days_until_expiry(self):
        if self.expires_at:
            from django.utils import timezone
            delta = self.expires_at - timezone.now()
            return max(0, delta.days)
        return self.validity_period
class AIPolicyRecommendationInteraction(BaseModel):
    
    INTERACTION_TYPE_CHOICES = [
        ('viewed', 'Viewed'),
        ('clicked', 'Clicked'),
        ('shared', 'Shared'),
        ('downloaded', 'Downloaded'),
        ('inquired', 'Inquired'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    
    recommendation = models.ForeignKey(
        AIPolicyRecommendation,
        on_delete=models.CASCADE,
        related_name='interactions',
        help_text="The recommendation this interaction is about"
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPE_CHOICES,
        help_text="Type of interaction"
    )
    interaction_details = models.JSONField(
        default=dict,
        help_text="Additional details about the interaction"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string from the interaction"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user during interaction"
    )
    interaction_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this interaction occurred"
    )
    class Meta:
        db_table = 'ai_policy_recommendation_interactions'
        ordering = ['-interaction_at']
        indexes = [
            models.Index(fields=['recommendation', 'interaction_type']),
            models.Index(fields=['interaction_at']),
        ]
    
    def __str__(self):
        return f"{self.interaction_type} - {self.recommendation.recommendation_title}"
