from django.db import models
from django.contrib.auth import get_user_model
from apps.customers.models import Customer

User = get_user_model()


class CustomerFile(models.Model):
    """Model to store customer file information based on the schema provided"""

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
        ]
    
    def __str__(self):
        return f"File: {self.file_name} - Customer: {self.customer}"
    
    @property
    def customer_name(self):
        """Return the customer name for easy access"""
        if self.customer:
            return f"{self.customer.first_name} {self.customer.last_name}".strip()
        return None

    @property
    def document_type(self):
        """Return the document type for easy access"""
        # This would need to be implemented with a database query if needed
        return None
    
    def get_file_size_display(self):
        """Return human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
