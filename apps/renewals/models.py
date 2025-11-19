from django.db import models
from django.contrib.auth import get_user_model
from apps.customers.models import Customer
from apps.policies.models import Policy
from apps.core.models import BaseModel
from apps.customer_payments.models import CustomerPayment
from apps.channels.models import Channel 
from apps.teams.models import Team
User = get_user_model()

class RenewalCase(BaseModel):
    """Model for tracking policy renewal cases"""

    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('renewed', 'Renewed'),
        ('not_interested', 'Not Interested'),
        ('dnc_email', 'DNC email'),
        ('dnc_whatsapp', 'DNC WhatsApp'),
        ('dnc_sms', 'DNC SMS'),
        ('dnc_call', 'DNC Call'),
        ('dnc_bot_calling', 'DNC Bot Calling'),
        ('payment_failed', 'Payment Failed'),
        ('customer_postponed', 'Customer Postponed'),
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
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_renewal_cases', db_column='assigned_to')
    assigned_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renewal_cases"
    )
    
    renewal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], default='pending', help_text="Payment status - auto-generated from customer_payments table")

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
    
    follow_up_date = models.DateField(null=True, blank=True, help_text="Date for the next follow-up")
    follow_up_time = models.TimeField(null=True, blank=True, help_text="Time for the next follow-up")
    remarks = models.TextField(blank=True, help_text="Additional remarks or notes for the case")
    
    class Meta:
        db_table = 'renewal_cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to']),
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