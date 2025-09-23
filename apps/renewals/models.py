from django.db import models
from django.contrib.auth import get_user_model
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.core.models import BaseModel
from apps.channels.models import Channel
from apps.customer_payments.models import CustomerPayment

User = get_user_model()

class RenewalCase(BaseModel):
    """Model for tracking policy renewal cases"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('renewed', 'Renewed'),
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
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_renewal_cases', db_column='assigned_to')
    
    renewal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], default='pending', help_text="Payment status - auto-generated from customer_payments table")
    
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

    customer_payment = models.ForeignKey(
        CustomerPayment,
        on_delete=models.SET_NULL,  
        null=True,
        blank=True,
        related_name='renewal_cases',
        db_column='customer_payment_id',
        help_text="Payment record associated with this renewal case"
    )
    

    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'renewal_cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['channel_id']),
            models.Index(fields=['batch_code']),
        ]
        
    def __str__(self):
        return f"{self.case_number} - {self.customer.full_name}"
    
    @property
    def communication_attempts_count(self):
        """Calculate communication attempts from CommunicationLog records"""
        from apps.customer_communication_preferences.models import CommunicationLog
        return CommunicationLog.objects.filter(customer=self.customer).count()
    
    def get_communication_attempts(self):
        """Get the actual communication attempts count from logs"""
        return self.communication_attempts_count
    
    @property
    def priority(self):
        """Get priority - always returns 'medium' for backward compatibility"""
        return 'medium'
    
    def get_priority_display(self):
        """Get priority display name - always returns 'Medium' for backward compatibility"""
        return 'Medium'
    
    @property
    def last_contact_date(self):
        """Get the last contact date from CommunicationLog records"""
        from apps.customer_communication_preferences.models import CommunicationLog
        latest_communication = CommunicationLog.objects.filter(
            customer=self.customer,
            is_deleted=False
        ).order_by('-communication_date').first()
        return latest_communication.communication_date if latest_communication else None