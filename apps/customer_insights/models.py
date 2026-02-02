from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.customers.models import Customer

User = get_user_model()
class CustomerInsight(BaseModel):
    """Main customer insights aggregation - simplified single table approach"""
    
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='customer_insights',
        help_text="Customer these insights belong to",
    )
    
    calculated_at = models.DateTimeField(
        auto_now=True,
        help_text="When these insights were last calculated"
    )
    
    payment_insights = models.JSONField(
        default=dict,
        help_text="Payment-related insights and metrics"
    )
    
    communication_insights = models.JSONField(
        default=dict,
        help_text="Communication-related insights and metrics"
    )
    
    claims_insights = models.JSONField(
        default=dict,
        help_text="Claims-related insights and metrics"
    )
    
    profile_insights = models.JSONField(
        default=dict,
        help_text="Customer profile and behavioral insights"
    )
    
    is_cached = models.BooleanField(
        default=False,
        help_text="Whether insights are cached and up-to-date"
    )
    
    cache_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the cached insights expire"
    )
    
    class Meta:
        db_table = 'customer_insights'
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['calculated_at']),
            models.Index(fields=['is_cached']),
        ]
    
    def __str__(self):
        return f"Insights for {self.customer}"
    
    @property
    def is_expired(self):
        """Check if cached insights are expired"""
        if not self.is_cached or not self.cache_expires_at:
            return True
        from django.utils import timezone
        return timezone.now() > self.cache_expires_at