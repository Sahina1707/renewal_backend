"""
File upload models for the Intelipro Insurance Policy Renewal System.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from apps.core.models import BaseModel
import os
import uuid

User = get_user_model()


def upload_path(instance, filename):
    """Generate upload path for files"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join(instance.category, timezone.now().strftime('%Y/%m/%d'), filename)


class FileUpload(BaseModel):
    """Model for tracking all file uploads"""
    
    CATEGORY_CHOICES = [
        ('avatar', 'User Avatar'),
        ('policy', 'Policy Document'),
        ('claim', 'Claim Document'),
        ('customer', 'Customer Document'),
        ('campaign', 'Campaign Asset'),
        ('email', 'Email Attachment'),
        ('survey', 'Survey Asset'),
        ('report', 'Report File'),
        ('import', 'Data Import'),
        ('export', 'Data Export'),
        ('template', 'Template File'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('quarantine', 'Quarantine'),
        ('deleted', 'Deleted'),
    ]
    
    # File information
    file = models.FileField(upload_to=upload_path, max_length=500)
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=64, unique=True, help_text="SHA-256 hash")
    
    # Categorization
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    subcategory = models.CharField(max_length=50, blank=True, db_index=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Status and processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading', db_index=True)
    processing_result = models.TextField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Security
    is_public = models.BooleanField(default=False)
    virus_scan_result = models.CharField(max_length=20, blank=True)
    virus_scan_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True, help_text="Alt text for images")
    
    # Usage tracking
    download_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'uploads_fileupload'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['created_by', 'category']),
            models.Index(fields=['file_hash']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.original_name} ({self.category})"
    
    @property
    def file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.original_name)[1].lower()
    
    @property
    def is_image(self):
        """Check if file is an image"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        return self.file_extension in image_extensions
    
    @property
    def is_document(self):
        """Check if file is a document"""
        doc_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
        return self.file_extension in doc_extensions
    
    @property
    def formatted_size(self):
        """Return human-readable file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"
    
    def increment_download_count(self):
        """Increment download count"""
        self.download_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['download_count', 'last_accessed'])
    
    def is_expired(self):
        """Check if file is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class FileShare(BaseModel):
    """Model for sharing files with external users"""
    
    file = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name='shares')
    share_token = models.UUIDField(default=uuid.uuid4, unique=True)
    shared_with_email = models.EmailField(blank=True)
    shared_with_name = models.CharField(max_length=100, blank=True)
    
    # Access control
    requires_password = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=255, blank=True)
    max_downloads = models.PositiveIntegerField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    
    # Expiration
    expires_at = models.DateTimeField()
    
    # Tracking
    last_accessed = models.DateTimeField(null=True, blank=True)
    access_log = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'uploads_fileshare'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['share_token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Share: {self.file.original_name} with {self.shared_with_email or 'Anonymous'}"
    
    def is_expired(self):
        """Check if share is expired"""
        return timezone.now() > self.expires_at
    
    def is_download_limit_reached(self):
        """Check if download limit is reached"""
        if self.max_downloads:
            return self.download_count >= self.max_downloads
        return False
    
    def can_access(self):
        """Check if share can be accessed"""
        return not (self.is_expired() or self.is_download_limit_reached())
    
    def record_access(self, ip_address=None, user_agent=None):
        """Record access to the shared file"""
        access_record = {
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        
        if not self.access_log:
            self.access_log = []
        
        self.access_log.append(access_record)
        self.download_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['access_log', 'download_count', 'last_accessed'])


class ImageVariant(models.Model):
    """Model for storing different variants/sizes of images"""
    
    VARIANT_CHOICES = [
        ('thumbnail', 'Thumbnail'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('original', 'Original'),
    ]
    
    original_file = models.ForeignKey(
        FileUpload,
        on_delete=models.CASCADE,
        related_name='variants',
        limit_choices_to={'mime_type__startswith': 'image/'}
    )
    variant_type = models.CharField(max_length=20, choices=VARIANT_CHOICES)
    file = models.ImageField(upload_to='variants/')
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    file_size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'uploads_imagevariant'
        unique_together = ['original_file', 'variant_type']
        ordering = ['variant_type']
    
    def __str__(self):
        return f"{self.original_file.original_name} - {self.variant_type} ({self.width}x{self.height})"


class UploadSession(BaseModel):
    """Model for tracking multi-part/chunked uploads"""
    
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=FileUpload.CATEGORY_CHOICES)
    
    # Upload progress
    chunks_total = models.PositiveIntegerField()
    chunks_uploaded = models.PositiveIntegerField(default=0)
    bytes_uploaded = models.PositiveBigIntegerField(default=0)
    
    # Status
    is_completed = models.BooleanField(default=False)
    completed_file = models.OneToOneField(
        FileUpload,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='upload_session'
    )
    
    # Metadata
    chunk_info = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'uploads_uploadsession'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['created_by', 'is_completed']),
        ]
    
    def __str__(self):
        return f"Upload session: {self.filename} ({self.chunks_uploaded}/{self.chunks_total})"
    
    @property
    def progress_percentage(self):
        """Calculate upload progress percentage"""
        if self.chunks_total == 0:
            return 0
        return (self.chunks_uploaded / self.chunks_total) * 100
    
    def is_expired(self):
        """Check if upload session is expired"""
        return timezone.now() > self.expires_at


class FileProcessingQueue(models.Model):
    """Queue for background file processing tasks"""
    
    TASK_CHOICES = [
        ('virus_scan', 'Virus Scan'),
        ('image_resize', 'Image Resize'),
        ('pdf_extract', 'PDF Text Extraction'),
        ('metadata_extract', 'Metadata Extraction'),
        ('thumbnail_generate', 'Thumbnail Generation'),
        ('compress', 'File Compression'),
        ('convert', 'Format Conversion'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    file = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name='processing_tasks')
    task_type = models.CharField(max_length=20, choices=TASK_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.PositiveIntegerField(default=5, help_text="1=highest, 10=lowest")
    
    # Task details
    task_params = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Retry logic
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    class Meta:
        db_table = 'uploads_fileprocessingqueue'
        ordering = ['priority', 'created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['task_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.task_type} for {self.file.original_name} - {self.status}"


class UploadFile(BaseModel):
    """Model for tracking policy data uploads and batch processing"""
    
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('xlsx', 'Excel File'),
        ('csv', 'CSV File'),
        ('json', 'JSON File'),
        ('xml', 'XML File'),
    ]
    
    # File information
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveBigIntegerField(help_text="File size in bytes")
    file_path = models.CharField(max_length=500, help_text="Path to uploaded file")
    
    # Processing information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading', db_index=True)
    total_records = models.PositiveIntegerField(default=0, help_text="Total records in file")
    successful_records = models.PositiveIntegerField(default=0, help_text="Successfully processed records")
    failed_records = models.PositiveIntegerField(default=0, help_text="Failed to process records")
    skipped_records = models.PositiveIntegerField(default=0, help_text="Skipped records")
    
    # Processing details
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.DurationField(null=True, blank=True, help_text="Total processing time")
    
    # Error handling
    error_message = models.TextField(blank=True, help_text="Error message if processing failed")
    error_details = models.JSONField(default=dict, blank=True, help_text="Detailed error information")
    validation_errors = models.JSONField(default=list, blank=True, help_text="Validation errors found")
    
    # Results
    processing_result = models.JSONField(default=dict, blank=True, help_text="Processing results and statistics")
    created_objects = models.JSONField(default=dict, blank=True, help_text="Objects created during processing")
    updated_objects = models.JSONField(default=dict, blank=True, help_text="Objects updated during processing")
    
    # Metadata
    upload_session_id = models.CharField(max_length=100, blank=True, help_text="Upload session identifier")
    batch_id = models.CharField(max_length=100, blank=True, help_text="Batch processing identifier")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata")
    
    # Notifications
    notify_on_completion = models.BooleanField(default=True, help_text="Send notification when processing completes")
    notify_email = models.EmailField(blank=True, help_text="Email to send notifications to")
    
    class Meta:
        db_table = 'uploads_uploadfile'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['file_type', 'status']),
            models.Index(fields=['upload_session_id']),
            models.Index(fields=['batch_id']),
        ]
    
    def __str__(self):
        return f"{self.file_name} - {self.get_status_display()}"
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_records == 0:
            return 0
        return (self.successful_records / self.total_records) * 100
    
    @property
    def failure_rate(self):
        """Calculate failure rate percentage"""
        if self.total_records == 0:
            return 0
        return (self.failed_records / self.total_records) * 100
    
    @property
    def formatted_file_size(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def mark_as_processing(self):
        """Mark file as processing"""
        self.status = 'processing'
        self.processing_started_at = timezone.now()
        self.save(update_fields=['status', 'processing_started_at'])
    
    def mark_as_completed(self, successful_count=0, failed_count=0, skipped_count=0):
        """Mark file processing as completed"""
        self.status = 'completed'
        self.processing_completed_at = timezone.now()
        self.successful_records = successful_count
        self.failed_records = failed_count
        self.skipped_records = skipped_count
        
        if self.processing_started_at:
            self.processing_time = self.processing_completed_at - self.processing_started_at
        
        self.save(update_fields=[
            'status', 'processing_completed_at', 'successful_records', 
            'failed_records', 'skipped_records', 'processing_time'
        ])
    
    def mark_as_failed(self, error_message, error_details=None):
        """Mark file processing as failed"""
        self.status = 'failed'
        self.processing_completed_at = timezone.now()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        
        if self.processing_started_at:
            self.processing_time = self.processing_completed_at - self.processing_started_at
        
        self.save(update_fields=[
            'status', 'processing_completed_at', 'error_message', 
            'error_details', 'processing_time'
        ])
    
    def add_validation_error(self, row_number, field, message):
        """Add a validation error"""
        if not self.validation_errors:
            self.validation_errors = []
        
        self.validation_errors.append({
            'row': row_number,
            'field': field,
            'message': message
        })
        self.save(update_fields=['validation_errors'])
    
    def update_processing_result(self, result_data):
        """Update processing result data"""
        self.processing_result.update(result_data)
        self.save(update_fields=['processing_result'])
    
    def is_processing_complete(self):
        """Check if processing is complete"""
        return self.status in ['completed', 'failed', 'cancelled'] 