from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q 

User = get_user_model()
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
class Audience(models.Model):
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, unique=True, help_text="e.g., Policy Holders - Expiring Q4")
    description = models.TextField(blank=True, help_text="A brief description of the audience criteria.")
    
    segments = models.JSONField(default=list, help_text="List of comma-separated segments/tags (e.g., High Value, Auto Insurance)")
    
    contact_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_audiences')
    metadata = models.JSONField(default=dict, blank=True, help_text="Extra metadata, e.g., uploaded file hashes")
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_audiences')
    
    class Meta:
        db_table = 'audience_manager_audiences'
        ordering = ['name']
        verbose_name = 'Audience'
        verbose_name_plural = 'Audiences'
        
    def __str__(self):
        return self.name

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
        self.contacts.filter(is_deleted=False).update(
            is_deleted=True,
            deleted_at=timezone.now(),
            deleted_by=user
        )
class AudienceContact(models.Model):
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    id = models.BigAutoField(primary_key=True)
    audience = models.ForeignKey(Audience, on_delete=models.CASCADE, related_name='contacts')
    
    name = models.CharField(max_length=200)
    expiry_date = models.DateField(null=True, blank=True, help_text="Policy expiry date")
    email = models.EmailField(help_text="Primary email address for campaigning", blank=True, null=True) # Make blank/null true
    phone = models.CharField(max_length=20, blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_audience_contacts')
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_audience_contacts')
    class Meta:
        db_table = 'audience_manager_contacts'
        ordering = ['name']
        verbose_name = 'Audience Contact'
        verbose_name_plural = 'Audience Contacts'
        
        constraints = [
            models.UniqueConstraint(
                fields=['audience', 'email'], 
                name='unique_email_per_audience',
                condition=Q(email__isnull=False) 
            ),
            models.UniqueConstraint(
                fields=['audience', 'phone'], 
                name='unique_phone_per_audience',
                condition=Q(phone__isnull=False)
            )
        ]
        
    def __str__(self):
        return f"{self.name} ({self.email or self.phone})"
    
    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])