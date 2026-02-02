from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, EmailValidator
from django.utils import timezone
from apps.core.models import BaseModel
import uuid

User = get_user_model()
class CustomerSegment(BaseModel):
    """Model for customer segmentation"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    criteria = models.JSONField(
        default=dict,
        help_text="Segmentation criteria in JSON format"
    )
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_customer_count(self):
        """Get number of customers in this segment"""
        return self.customers.filter(is_deleted=False).count()

class Customer(BaseModel):
    """Main customer model"""
    
    CUSTOMER_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('corporate', 'Corporate'),
        ('sme', 'Small & Medium Enterprise'),
        ('government', 'Government'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('prospect', 'Prospect'),
        ('dormant', 'Dormant'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('vip', 'VIP'),
    ]

    PROFILE_CHOICES = [
        ('Normal', 'Normal'),
        ('HNI', 'HNI (High Net-Worth Individual)'),
    ]
    
    # Basic Information
    customer_code = models.CharField(max_length=20, unique=True, db_index=True, help_text="Auto-generated customer code like CUS2025001")
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='individual')
    
    # Personal/Company Details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    title = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        blank=True
    )
    
    # Contact Information
    email = models.EmailField(validators=[EmailValidator()], db_index=True)
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
        db_index=True
    )
    alternate_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')]
    )
    
    # Address Information
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    state = models.CharField(max_length=100, blank=True, db_index=True)
    postal_code = models.CharField(max_length=20, blank=True, db_index=True)
    country = models.CharField(max_length=100, default='India', db_index=True)
    
    # Business Information (for corporate customers)
    industry = models.CharField(max_length=100, blank=True, db_index=True)
    business_registration_number = models.CharField(max_length=50, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    
    # Customer Management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', db_index=True)
    profile = models.CharField(max_length=10, choices=PROFILE_CHOICES, default='Normal', db_index=True, help_text="Customer profile based on policy count")
    assigned_agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_customers'
    )
    channel_id = models.ForeignKey(
        'business_channels.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        db_column='channel_id',
        help_text="Channel associated with this customer"
    )
    segment = models.ForeignKey(
        CustomerSegment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers'
    )
    
    # Preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('whatsapp', 'WhatsApp'),
        ],
        default='email'
    )
    preferred_language = models.CharField(max_length=50, default='English')
    document_language = models.CharField(max_length=50, default='English')
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    
    # Communication Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    whatsapp_notifications = models.BooleanField(default=False)
    marketing_communications = models.BooleanField(default=True)
    
    # KYC Information
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
        ],
        default='pending',
        help_text="KYC verification status from Excel"
    )
    kyc_documents = models.CharField(max_length=200, blank=True, help_text="KYC documents list from Excel")
    
    # Verification Status (Bureau API)
    email_verified = models.BooleanField(default=False, db_index=True, help_text="Whether the email has been verified")
    phone_verified = models.BooleanField(default=False, db_index=True, help_text="Whether the phone number has been verified")
    pan_verified = models.BooleanField(default=False, db_index=True, help_text="Whether the PAN number has been verified")
    email_verified_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when email was verified")
    phone_verified_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when phone was verified")
    pan_verified_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when PAN was verified")
    pan_number = models.CharField(blank=True, max_length=10, help_text="PAN number for verification")

    # Financial Information
    credit_score = models.PositiveIntegerField(null=True, blank=True)
    payment_terms = models.CharField(max_length=50, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Important Dates
    first_policy_date = models.DateField(null=True, blank=True)
    last_policy_date = models.DateField(null=True, blank=True)
    last_contact_date = models.DateTimeField(null=True, blank=True)
    next_followup_date = models.DateTimeField(null=True, blank=True)
    
    # Metrics
    total_policies = models.PositiveIntegerField(default=0)
    total_premium = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    lifetime_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Additional Information
    internal_notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer_code']),
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['city', 'state']),
            models.Index(fields=['assigned_agent']),
            models.Index(fields=['channel_id']),
            models.Index(fields=['segment']),
            models.Index(fields=['first_policy_date']),
            models.Index(fields=['kyc_status']),
            models.Index(fields=['email_verified']),
            models.Index(fields=['phone_verified']),
            models.Index(fields=['pan_verified']),
        ]
    
    def __str__(self):
        if self.customer_type == 'individual':
            return f"{self.first_name} {self.last_name} ({self.customer_code})"
        else:
            return f"{self.company_name} ({self.customer_code})"
    
    @property
    def full_name(self):
        """Return customer's full name"""
        if self.customer_type == 'individual':
            return f"{self.first_name} {self.last_name}".strip()
        return self.company_name
    
    @property
    def display_name(self):
        """Return display name for UI"""
        name = self.full_name
        if self.title:
            name = f"{self.title} {name}"
        return name
    
    @property
    def full_address(self):
        """Return formatted full address"""
        address_parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ', '.join(filter(None, address_parts))
    
    def get_active_policies_count(self):
        """Get count of active policies"""
        return self.policies.filter(status='active', is_deleted=False).count()
    
    def get_total_premium_current_year(self):
        """Get total premium for current year"""
        current_year = timezone.now().year
        return self.policies.filter(
            start_date__year=current_year,
            is_deleted=False
        ).aggregate(
            total=models.Sum('premium_amount')
        )['total'] or 0
    
    def update_metrics(self):
        """Update customer metrics"""
        policies = self.policies.filter(is_deleted=False)

        self.total_policies = policies.count()
        self.total_premium = policies.aggregate(
            total=models.Sum('premium_amount')
        )['total'] or 0

        self.lifetime_value = self.total_premium

        if self.total_policies > 1:
            self.profile = 'HNI'
        else:
            self.profile = 'Normal'

        # Update policy dates
        if policies.exists():
            self.first_policy_date = policies.order_by('start_date').first().start_date
            self.last_policy_date = policies.order_by('-start_date').first().start_date

        self.save(update_fields=[
            'total_policies', 'total_premium', 'lifetime_value',
            'first_policy_date', 'last_policy_date', 'profile'
        ])


class CustomerContact(BaseModel):
    """Additional contacts for customers (family members, employees, etc.)"""
    
    RELATIONSHIP_CHOICES = [
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
        ('employee', 'Employee'),
        ('partner', 'Business Partner'),
        ('authorized_person', 'Authorized Person'),
        ('other', 'Other'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    email = models.EmailField(blank=True)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')]
    )
    is_primary = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)
    can_make_changes = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-is_primary', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.relationship}) - {self.customer}"


class CustomerDocument(BaseModel):
    """Documents associated with customers"""
    
    DOCUMENT_TYPE_CHOICES = [
        ('id_proof', 'ID Proof'),
        ('address_proof', 'Address Proof'),
        ('income_proof', 'Income Proof'),
        ('business_registration', 'Business Registration'),
        ('tax_document', 'Tax Document'),
        ('bank_statement', 'Bank Statement'),
        ('medical_report', 'Medical Report'),
        ('photo', 'Photograph'),
        ('signature', 'Signature'),
        ('authorization', 'Authorization Letter'),
        ('other', 'Other'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, db_index=True)
    document_number = models.CharField(max_length=100, blank=True)
    file = models.ForeignKey(
        'uploads.FileUpload',
        on_delete=models.CASCADE,
        related_name='customer_documents'
    )
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_customer_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Expiration
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Additional info
    issuing_authority = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'document_type']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.customer} - {self.get_document_type_display()}"
    
    def is_expired(self):
        """Check if document is expired"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False
    
    def days_until_expiry(self):
        """Get days until document expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None


class CustomerInteraction(BaseModel):
    """Track all interactions with customers"""
    
    INTERACTION_TYPE_CHOICES = [
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('meeting', 'Meeting'),
        ('visit', 'Site Visit'),
        ('complaint', 'Complaint'),
        ('inquiry', 'Inquiry'),
        ('claim', 'Claim'),
        ('renewal', 'Renewal'),
        ('other', 'Other'),
    ]
    
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]
    
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
        ('no_response', 'No Response'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='interactions')
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES, db_index=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    
    # Interaction details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    outcome = models.TextField(blank=True)
    
    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Follow-up
    requires_followup = models.BooleanField(default=False)
    followup_date = models.DateTimeField(null=True, blank=True)
    followup_notes = models.TextField(blank=True)
    
    attachments = models.ManyToManyField(
        'uploads.FileUpload',
        blank=True,
        related_name='customer_interactions'
    )
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'interaction_type']),
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['requires_followup', 'followup_date']),
        ]
    
    def __str__(self):
        return f"{self.customer} - {self.get_interaction_type_display()} ({self.created_at.date()})"


class CustomerNote(BaseModel):
    """Internal notes about customers"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_private = models.BooleanField(default=False, help_text="Only visible to creator")
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'priority']),
            models.Index(fields=['created_by', 'is_private']),
        ]
    
    def __str__(self):
        return f"{self.customer} - {self.title}" 