from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.customers.models import Customer

User = get_user_model()


class CustomerFile(models.Model):
    """Model to store customer file information based on the schema provided"""

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
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID'),
        ('pan_card', 'PAN Card'),
        ('aadhar_card', 'Aadhar Card'),
        ('utility_bill', 'Utility Bill'),
        ('rental_agreement', 'Rental Agreement'),
        ('property_document', 'Property Document'),
        ('salary_slip', 'Salary Slip'),
        ('form_16', 'Form 16'),
        ('itr', 'Income Tax Return'),
        ('other', 'Other'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='customer_files',
        help_text="Customer who owns this file"
    )

    file_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original file name (e.g., policy_copy.pdf) - Auto-filled from uploaded file"
    )
    
    file_path = models.CharField(
        max_length=500,
        help_text="Path or URL where the file is stored"
    )
    
    file_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="MIME type (e.g., application/pdf, image/jpeg) - Auto-detected from file"
    )
    
    file_size = models.BigIntegerField(
        help_text="Size of the file in bytes"
    )
    
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        blank=True,
        null=True,
        db_index=True,
        help_text="Type of document"
    )
    
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the document has been verified"
    )
    
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when document was verified"
    )
    
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_customer_files',
        help_text="User who verified this document"
    )
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_customer_files',
        help_text="User who uploaded the file"
    )
    
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of upload"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_customer_files',
        help_text="Last user who updated the file"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Status flag for active/inactive files"
    )
    
    pan_number = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="PAN number extracted from document (if applicable)"
    )
    
    class Meta:
        db_table = 'customers_files'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
            models.Index(fields=['file_type', 'is_active']),
            models.Index(fields=['document_type', 'is_verified']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['customer', 'is_verified']),
        ]
    
    def __str__(self):
        return f"File: {self.file_name} - Customer: {self.customer}"
    
    @property
    def customer_name(self):
        """Return the customer name for easy access"""
        if self.customer:
            return f"{self.customer.first_name} {self.customer.last_name}".strip()
        return None
    
    def verify(self, user=None):
        """Mark the document as verified"""
        self.is_verified = True
        self.verified_at = timezone.now()
        if user:
            self.verified_by = user
        self.save()
    
    def get_file_size_display(self):
        """Return human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
