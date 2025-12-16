# whatsapp_flow_management/models.py

from django.db import models
from django.conf import settings

# --- Soft Delete Abstract Base ---
class SoftDeleteBase(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Standard Audit Fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='created_%(class)ss' # Dynamically named relation
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='updated_%(class)ss'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_%(class)ss')

    class Meta:
        abstract = True

# --- 1. WhatsApp Flow Model (The Flow Container) ---
class WhatsAppFlow(SoftDeleteBase):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('PAUSED', 'Paused'),
        ('ARCHIVED', 'Archived'),
    ]
    TRIGGER_CHOICES = [
        ('INBOUND', 'Inbound Message Trigger'),
        ('POST_CAMPAIGN', 'Post-Campaign Follow-up'),
        ('SCHEDULED', 'Scheduled Trigger'),
        ('API', 'API Trigger'),
    ]

    name = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    entry_point = models.CharField(max_length=50, choices=TRIGGER_CHOICES, default='INBOUND')
    
    # Store the entire canvas layout and connections as JSON
    canvas_layout = models.JSONField(default=dict)
    
    
    def __str__(self):
        return self.name

# --- 2. Flow Block Model (Individual Nodes on the Canvas) ---
class FlowBlock(models.Model):
    BLOCK_TYPE_CHOICES = [
        ('SEND_MESSAGE', 'Send Message'),
        ('COLLECT_INPUT', 'Collect Input'),
        ('BUTTONS', 'Buttons'),
        ('API_CALL', 'API Call'),
        ('CONDITIONAL_LOGIC', 'Conditional Logic'),
        ('TEMPLATE', 'Use Template'),
    ]

    flow = models.ForeignKey(WhatsAppFlow, on_delete=models.CASCADE, related_name='blocks')
    block_id = models.CharField(max_length=50, db_index=True) 
    block_type = models.CharField(max_length=50, choices=BLOCK_TYPE_CHOICES)
    configuration = models.JSONField(default=dict)
    connections = models.JSONField(default=list) 

    class Meta:
        unique_together = ('flow', 'block_id')

    def __str__(self):
        return f"{self.flow.name} - {self.get_block_type_display()} ({self.block_id})"

# --- 3. Flow Analytics Model (Required for Dashboard Summary) ---
class FlowAnalytics(models.Model):
    flow = models.OneToOneField(
        WhatsAppFlow, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    
    total_recipients = models.PositiveIntegerField(default=0)
    messages_delivered = models.PositiveIntegerField(default=0)
    messages_replied = models.PositiveIntegerField(default=0)
    delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    reply_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Analytics for {self.flow.name}"

# --- 4. WhatsApp Message Templates Model (For Templates Tab) ---
class WhatsAppMessageTemplate(SoftDeleteBase):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    content_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# --- 5. Flow Templates Model (For Templates Tab) ---
class FlowTemplate(SoftDeleteBase):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    template_flow_json = models.JSONField(default=dict)
    category = models.CharField(max_length=50, default='General')

    def __str__(self):
        return self.name