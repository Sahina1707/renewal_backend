from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import RegexValidator
from apps.core.models import BaseModel
from decimal import Decimal

User = get_user_model()

from apps.renewals.models import RenewalCase

Case = RenewalCase

def get_case_id(self):
    """Get case ID in the format expected by case history"""
    return self.case_number

def get_title(self):
    """Get case title from customer and policy info"""
    if self.customer and self.policy:
        return f"Renewal for {self.customer.full_name} - {self.policy.policy_number}"
    elif self.customer:
        return f"Renewal for {self.customer.full_name}"
    else:
        return f"Renewal Case {self.case_number}"

def get_description(self):
    """Get case description from notes"""
    return self.notes or f"Policy renewal case for {self.customer.full_name if self.customer else 'Unknown Customer'}"

def get_handling_agent(self):
    """Get handling agent (assigned_to field)"""
    return self.assigned_to

def get_started_at(self):
    """Get started date (created_at field)"""
    return self.created_at

def get_processing_days(self):
    """Calculate processing days"""
    if self.created_at:
        from django.utils import timezone
        now = timezone.now()
        if self.created_at.tzinfo is None:
            from django.utils import timezone
            created_at = timezone.make_aware(self.created_at)
        else:
            created_at = self.created_at
        delta = now - created_at
        return delta.days
    return 0

def get_closed_at(self):
    """Get closed date - check if status indicates closure"""
    if self.status in ['completed', 'renewed', 'cancelled', 'expired']:
        return self.updated_at
    return None

def get_is_closed(self):
    """Check if case is closed"""
    return self.status in ['completed', 'renewed', 'cancelled', 'expired']

def get_is_active(self):
    """Check if case is active"""
    return self.status not in ['completed', 'renewed', 'cancelled', 'expired']

def close_case(self, user=None):
    """Close the case"""
    self.status = 'completed'
    if user:
        self.updated_by = user
    self.save(update_fields=['status', 'updated_by', 'updated_at'])

# Add these properties to the RenewalCase model
RenewalCase.case_id = property(get_case_id)
RenewalCase.title = property(get_title)
RenewalCase.description = property(get_description)
RenewalCase.handling_agent = property(get_handling_agent)
RenewalCase.started_at = property(get_started_at)
RenewalCase.processing_days = property(get_processing_days)
RenewalCase.closed_at = property(get_closed_at)
RenewalCase.is_closed = property(get_is_closed)
RenewalCase.is_active = property(get_is_active)
RenewalCase.close_case = close_case


class CaseHistory(BaseModel):
    ACTION_CHOICES = [
        ('case_created', 'Case Created'),
        ('case_updated', 'Case Updated'),
        ('case_closed', 'Case Closed'),
        ('case_cancelled', 'Case Cancelled'),
        ('status_changed', 'Status Changed'),
        ('agent_assigned', 'Agent Assigned'),
        ('agent_unassigned', 'Agent Unassigned'),
        ('validation', 'Validation'),
        ('assignment', 'Assignment'),
        ('comment_added', 'Comment Added'),
        ('comment_updated', 'Comment Updated'),
        ('comment_deleted', 'Comment Deleted'),
        ('document_uploaded', 'Document Uploaded'),
        ('document_removed', 'Document Removed'),
        ('communication_sent', 'Communication Sent'),
        ('follow_up_scheduled', 'Follow-up Scheduled'),
        ('escalation', 'Escalation'),
        ('other', 'Other'),
    ]
    
    case = models.ForeignKey(
        RenewalCase,
        on_delete=models.CASCADE,
        related_name='case_history',
        help_text="Case this history entry belongs to"
    )
    
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        db_index=True,
        help_text="Type of action performed"
    )
    
    description = models.TextField(
        help_text="Detailed description of the action"
    )
    
    # Additional context
    old_value = models.TextField(
        blank=True,
        help_text="Previous value (for updates)"
    )
    new_value = models.TextField(
        blank=True,
        help_text="New value (for updates)"
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for this history entry"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case', 'action']),
            models.Index(fields=['case', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['created_by']),
        ]
        verbose_name = 'Case History'
        verbose_name_plural = 'Case Histories'
    
    def __str__(self):
        return f"{self.case.case_id} - {self.get_action_display()} ({self.created_at})"


