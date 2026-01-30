
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True

class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_deleted_objects'
    )

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, user=None):
        """Soft delete the object"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the object"""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()

class BaseModel(TimestampedModel, SoftDeleteModel):
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created_objects'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated_objects'
    )

    class Meta:
        abstract = True

class AuditLog(TimestampedModel):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view', 'View'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('send', 'Send'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    object_repr = models.TextField(null=True, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    additional_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action', 'created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} at {self.created_at}"


class SystemConfiguration(TimestampedModel):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField()
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    category = models.CharField(max_length=50, db_index=True)

    class Meta:
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.category}.{self.key}"

class APIRateLimit(TimestampedModel):
    """
    Model to track API rate limiting.
    """
    identifier = models.CharField(max_length=255, db_index=True)  
    endpoint = models.CharField(max_length=255, db_index=True)
    request_count = models.PositiveIntegerField(default=1)
    window_start = models.DateTimeField(default=timezone.now)
    is_blocked = models.BooleanField(default=False)

    class Meta:
        unique_together = ['identifier', 'endpoint', 'window_start']
        indexes = [
            models.Index(fields=['identifier', 'window_start']),
            models.Index(fields=['endpoint', 'window_start']),
        ]

    def __str__(self):
        return f"{self.identifier} - {self.endpoint} ({self.request_count} requests)" 