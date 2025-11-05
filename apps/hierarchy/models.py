"""
Hierarchy Management models for the Intelipro Insurance Policy Renewal System.
Manages organizational hierarchy including departments, regions, states, branches, and teams.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from apps.core.models import BaseModel
from decimal import Decimal
from django.core.exceptions import ValidationError

User = get_user_model()


class HierarchyManagement(BaseModel):
    UNIT_TYPE_CHOICES = [
        ('department', 'Department'),
        ('region', 'Region'),
        ('north_region', 'North Region'),
        ('state', 'State'),
        ('branch', 'Branch'),
        ('team', 'Team'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('restructuring', 'Restructuring'),
    ]
    
    # Basic Information
    unit_name = models.CharField(max_length=200, db_index=True)
    unit_type = models.CharField(
        max_length=30, 
        choices=UNIT_TYPE_CHOICES, 
        default='department',
        db_index=True
    )
    description = models.TextField(blank=True)
    
    PARENT_UNIT_CHOICES = [
        ('none', 'None (Root Level)'),
        ('north_region', 'North Region (region)'),
        ('delhi_state', 'Delhi State (state)'),
        ('connaught_place_branch', 'Connaught Place Branch (branch)'),
        ('renewals_department', 'Renewals Department (department)'),
        ('senior_renewal_team', 'Senior Renewal Team (team)'),
    ]

    parent_unit = models.CharField(
        max_length=50,
        choices=PARENT_UNIT_CHOICES,
        default='none',
        help_text="Parent unit in the hierarchy. Select 'None' for root level units."
    )
    
    # Manager Information
    manager_id = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^mgr-\d{3}$', 'Manager ID must be in format mgr-XXX')],
        unique=True,
        help_text="Manager ID in format mgr-XXX (e.g., mgr-002)"
    )
    
    # Financial Information
    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Budget allocated to this unit"
    )
    
    # Performance Metrics
    target_cases = models.PositiveIntegerField(
        default=0,
        help_text="Target number of cases for this unit"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )
    
    class Meta:
        db_table = 'hierarchy_management'
        ordering = ['unit_type', 'unit_name']
        verbose_name = 'Hierarchy Management'
        verbose_name_plural = 'Hierarchy Management'
        indexes = [
            models.Index(fields=['unit_type', 'status']),
            models.Index(fields=['parent_unit', 'unit_type']),
            models.Index(fields=['manager_id']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['unit_name', 'unit_type', 'parent_unit'],
                name='unique_unit_in_parent'
            ),
        ]
    
    def __str__(self):
        return f"{self.get_unit_type_display()}: {self.unit_name}"
    
    def clean(self):
        if self.parent_unit not in dict(self.PARENT_UNIT_CHOICES):
            raise ValidationError("Invalid parent unit choice.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
