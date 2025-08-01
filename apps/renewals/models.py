from django.db import models
from django.contrib.auth import get_user_model
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.core.models import BaseModel
from apps.channels.models import Channel

User = get_user_model()

class RenewalCase(BaseModel):
    """Model for tracking policy renewal cases"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('due', 'Due'),
        ('overdue', 'Overdue'),
        ('not_required', 'Not Required'),
        ('assigned', 'Assigned'),
        ('failed', 'Failed'),
        ('uploaded', 'Uploaded'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    case_number = models.CharField(max_length=100, unique=True)
    batch_code = models.CharField(max_length=50, help_text="Batch code for tracking Excel import batches (e.g., BATCH-2025-07-25-A)")
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='renewal_cases')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='renewal_cases')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_renewal_cases', db_column='assigned_to')
    
    renewal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    
    communication_attempts = models.IntegerField(default=0)
    last_contact_date = models.DateTimeField(null=True, blank=True)

    # Channel tracking
    channel_id = models.ForeignKey(
        Channel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewal_cases',
        help_text="Channel through which this renewal case was initiated",
        db_column='channel_id'
    )

    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'renewal_cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['channel_id']),
            models.Index(fields=['batch_code']),
        ]
        
    def __str__(self):
        return f"{self.case_number} - {self.customer.full_name}"
