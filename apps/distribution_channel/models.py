from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from decimal import Decimal


class DistributionChannel(BaseModel):
    """
    Model to manage distribution partners, agents, and sales channels.
    """
    
    CHANNEL_TYPE_CHOICES = [
        ('Agent Network', 'Agent Network'),
        ('Insurance Broker', 'Insurance Broker'),
        ('Bank Partnership', 'Bank Partnership'),
        ('Corporate Partner', 'Corporate Partner'),
        ('Online Platform', 'Online Platform'),
        ('Direct Sales', 'Direct Sales'),
    ]
    
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Pending', 'Pending'),
    ]
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Distribution channel name"
    )
    channel_type = models.CharField(
        max_length=50,
        choices=CHANNEL_TYPE_CHOICES,
        help_text="Type of distribution channel"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of the distribution channel"
    )
    
    # Foreign Key to channels table
    channel = models.ForeignKey(
        'business_channels.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='distribution_channels',
        help_text="Related communication channel"
    )
    
    # Contact Information
    contact_person = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Contact person name"
    )
    contact_email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
        validators=[EmailValidator()],
        help_text="Contact email address"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Geographical region covered"
    )
    
    # Financial Information
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Commission rate as a percentage (0-100)"
    )
    target_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Target revenue in currency"
    )
    
    # Status and Metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Active',
        help_text="Current status of the distribution channel"
    )
    partner_since = models.DateField(
        null=True,
        blank=True,
        help_text="Date when partnership started"
    )
    
    class Meta:
        db_table = 'distribution_channel'
        ordering = ['name']
        indexes = [
            models.Index(fields=['channel_type']),
            models.Index(fields=['status']),
            models.Index(fields=['region']),
            models.Index(fields=['channel']),
            models.Index(fields=['partner_since']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(commission_rate__gte=0, commission_rate__lte=100),
                name='valid_commission_rate'
            ),
            models.CheckConstraint(
                check=models.Q(target_revenue__gte=0),
                name='positive_target_revenue'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"
    
    @property
    def is_active(self):
        """Check if distribution channel is currently active"""
        return self.status == 'Active'
    
    def clean(self):
        """Additional model-level validation"""
        super().clean()
        
        # Validate commission rate if provided
        if self.commission_rate is not None:
            if self.commission_rate < 0 or self.commission_rate > 100:
                raise ValidationError({
                    'commission_rate': 'Commission rate must be between 0 and 100.'
                })
        
        # Validate target revenue if provided
        if self.target_revenue is not None and self.target_revenue < 0:
            raise ValidationError({
                'target_revenue': 'Target revenue cannot be negative.'
            })
