from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.renewals.models import RenewalCase

User = get_user_model()

class CaseLog(BaseModel):
    SUB_STATUS_CHOICES = [
        ('document_pending', 'Document Pending'),
        ('customer_contact_required', 'Customer Contact Required'),
        ('payment_processing', 'Payment Processing'),
        ('verification_in_progress', 'Verification In Progress'),
        ('approval_required', 'Approval Required'),
        ('ready_for_renewal', 'Ready For Renewal'),
        ('follow_up_required', 'Follow-up Required'),
        ('under_review', 'Under Review'),
    ]
    
    WORK_STEP_CHOICES = [
        ('initial_contact', 'Initial Contact'),
        ('document_collection', 'Document Collection'),
        ('verification', 'Verification'),
        ('premium_calculation', 'Premium Calculation'),
        ('payment_processing', 'Payment Processing'),
        ('policy_generation', 'Policy Generation'),
        ('final_review', 'Final Review'),
        ('delivery', 'Delivery'),
    ]
    
    renewal_case = models.ForeignKey(
        RenewalCase, 
        on_delete=models.CASCADE, 
        related_name='case_logs',
        help_text="Related renewal case"
    )
    
    sub_status = models.CharField(
        max_length=50, 
        choices=SUB_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Current sub-status of the case"
    )
    
    current_work_step = models.CharField(
        max_length=50, 
        choices=WORK_STEP_CHOICES,
        null=True,
        blank=True,
        help_text="Current work step in the renewal process"
    )
    
    next_follow_up_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date and time for next follow-up"
    )
    
    next_action_plan = models.TextField(
        blank=True,
        help_text="Description of the next planned action"
    )
    
    comment = models.TextField(
        blank=True,
        help_text="Additional comments or notes for this log entry"
    )
    
    class Meta:
        db_table = 'case_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['renewal_case', 'created_at']),
            models.Index(fields=['sub_status']),
            models.Index(fields=['current_work_step']),
            models.Index(fields=['next_follow_up_date']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Case Log'
        verbose_name_plural = 'Case Logs'
    
    def __str__(self):
        return f"Log for {self.renewal_case.case_number} - {self.get_sub_status_display()}"
    
    @property
    def is_follow_up_due(self):
        """Check if follow-up is due"""
        if not self.next_follow_up_date:
            return False
        from django.utils import timezone
        return timezone.now() >= self.next_follow_up_date
    
    @property
    def days_until_follow_up(self):
        """Calculate days until next follow-up"""
        if not self.next_follow_up_date:
            return None
        from django.utils import timezone
        delta = self.next_follow_up_date - timezone.now()
        return delta.days