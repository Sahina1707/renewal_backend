from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Audience(models.Model):
    """
    Represents a dynamic or static segment of contacts for targeting campaigns.
    Drives the cards seen in the Audience Manager interface.
    """
    
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, unique=True, help_text="e.g., Policy Holders - Expiring Q4")
    description = models.TextField(blank=True, help_text="A brief description of the audience criteria.")
    
    # Segmentation
    segments = models.JSONField(default=list, help_text="List of comma-separated segments/tags (e.g., High Value, Auto Insurance)")
    
    # Statistics
    contact_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)
    
    # Metadata for soft deletion and audit
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
    

class AudienceContact(models.Model):
    """
    Represents an individual contact belonging to an Audience segment.
    These are the rows seen in the Audience Details modal.
    """
    
    id = models.BigAutoField(primary_key=True)
    audience = models.ForeignKey(Audience, on_delete=models.CASCADE, related_name='contacts')
    
    # Core contact fields (as seen in the video's manual entry modal)
    name = models.CharField(max_length=200)
    email = models.EmailField(help_text="Primary email address for campaigning")
    phone = models.CharField(max_length=20, blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Metadata for soft deletion and audit
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_audience_contacts')
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_audience_contacts')
    
    class Meta:
        db_table = 'audience_manager_contacts'
        ordering = ['name']
        # Ensure a contact isn't duplicated within the same audience
        unique_together = ('audience', 'email') 
        verbose_name = 'Audience Contact'
        verbose_name_plural = 'Audience Contacts'
        
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])