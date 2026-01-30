from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import BaseModel
from apps.target_audience.models import TargetAudience
from decimal import Decimal

class Channel(BaseModel):
    
    CHANNEL_TYPE_CHOICES = [
        ('Online', 'Online'),
        ('Mobile', 'Mobile'),
        ('Offline', 'Offline'),
        ('Phone', 'Phone'),
        ('Agent', 'Agent'),
    ]

    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    name = models.CharField(max_length=255, help_text="Channel name")
    channel_type = models.CharField(
        max_length=20, 
        choices=CHANNEL_TYPE_CHOICES,
        help_text="Type of channel"
    )
    description = models.TextField(blank=True, help_text="Channel description")
    
    target_audience = models.ForeignKey(
        'target_audience.TargetAudience',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='channels',
        help_text="Target audience for this channel"
    )
    manager_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manager name for this channel"
    )
    
    cost_per_lead = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost per lead in currency"
    )
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Channel budget"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of the channel"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        help_text="Channel priority level"
    )
    working_hours = models.CharField(
        max_length=100,
        blank=True,
        help_text="Working hours for the channel (e.g., '9:00 AM - 5:00 PM')"
    )
    max_capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum capacity/throughput for the channel"
    )
    
    class Meta:
        db_table = 'channel'
        ordering = ['name']
        indexes = [
            models.Index(fields=['channel_type']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['manager_name']),
            models.Index(fields=['target_audience']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(cost_per_lead__gte=0),
                name='positive_cost_per_lead'
            ),
            models.CheckConstraint(
                check=models.Q(budget__gte=0),
                name='positive_budget'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"
    
    @property
    def is_active(self):
        """Check if channel is currently active"""
        return self.status == 'active'
    
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage if max_capacity is set"""
        if self.max_capacity and self.max_capacity > 0:
            return None
        return None
    
    def get_manager_name(self):
        """Get manager name"""
        return self.manager_name if self.manager_name else "No Manager Assigned"
    
    def get_target_audience_name(self):
        """Get target audience name"""
        if self.target_audience:
            return self.target_audience.name
        return "No Target Audience"
