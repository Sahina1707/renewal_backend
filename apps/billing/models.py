from django.db import models

class BillingPeriod(models.Model):
    month = models.IntegerField()
    year = models.IntegerField()
    is_active = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('month', 'year')
        db_table='billing_period'

    def __str__(self):
        return f"{self.month}/{self.year}"

class UsageCharge(models.Model):
    SERVICE_TYPES = [
        ('email', 'Email Notifications'),
        ('sms', 'SMS Notifications'),
        ('api', 'API Calls'),
        ('whatsapp', 'WhatsApp Business API'),
    ]
    
    period = models.ForeignKey(BillingPeriod, on_delete=models.CASCADE, related_name='usage_charges')
    service_name = models.CharField(max_length=50, choices=SERVICE_TYPES)
    count = models.IntegerField(default=0)
    rate_per_unit = models.DecimalField(max_digits=10, decimal_places=4) 
    
    class Meta:
        db_table='billing_usage_charge'
        
    @property
    def total_cost(self):
        return self.count * self.rate_per_unit

class PlatformCharge(models.Model):
    period = models.ForeignKey(BillingPeriod, on_delete=models.CASCADE, related_name='platform_charges')
    name = models.CharField(max_length=100) 
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, default="Monthly")

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('overdue', 'Overdue'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    download_url = models.URLField(blank=True, null=True) 
    
    class Meta:
        db_table='billing_invoice'
        
    def __str__(self):
        return self.invoice_number
    
class Vendor(models.Model):
    name = models.CharField(max_length=100)
    service_type = models.CharField(max_length=50)
    vendor_id = models.CharField(max_length=20, unique=True, blank=True) 
    contact_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    cost_per_message = models.DecimalField(max_digits=6, decimal_places=3, default=0.000)
    status = models.CharField(max_length=20, default="Active")
    def save(self, *args, **kwargs):
        if not self.vendor_id:
            last_vendor = Vendor.objects.order_by('-id').first()
            if last_vendor and last_vendor.vendor_id.startswith('VEN'):
                try:
                    last_number = int(last_vendor.vendor_id.replace('VEN', ''))
                    new_number = last_number + 1
                except ValueError:
                    new_number = 1
            else:
                new_number = 1
            self.vendor_id = f"VEN{new_number:03d}"   
        super().save(*args, **kwargs)
    class Meta:
        db_table='billing_vendor'
    def __str__(self):
        return self.name

class CommunicationLog(models.Model):
    """
    Records every single message sent. Used for 'Delivery Status' and 'Stats' tabs.
    """
    STATUS_CHOICES = [
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]
    case = models.ForeignKey(
        'renewals.RenewalCase', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='billing_logs'
    )
    
    customer = models.ForeignKey(
        'customers.Customer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='billing_logs'
    )
    policy_chatbot = models.ForeignKey(
        'policytimeline_chatbot.PolicyTimelineChatbot', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='billing_logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    type = models.CharField(max_length=50, choices=UsageCharge.SERVICE_TYPES)
    
    # Details for the "Delivery Status" table
    customer_name = models.CharField(max_length=100)
    message_snippet = models.CharField(max_length=255) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.CharField(max_length=255, blank=True, null=True)
    attempts = models.IntegerField(default=1)
    cost = models.DecimalField(max_digits=6, decimal_places=3)
    provider_message_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    class Meta:
        db_table='billing_communication'
        ordering = ['-timestamp']

class Campaign(models.Model):
    """
    For the 'Bulk Campaigns' toggle in the Delivery Status tab (Video 1:26)
    """
    name = models.CharField(max_length=100) 
    type = models.CharField(max_length=50, choices=UsageCharge.SERVICE_TYPES)
    total_recipients = models.IntegerField()
    successful_deliveries = models.IntegerField()
    failed_deliveries = models.IntegerField()
    status = models.CharField(max_length=20, default='Completed')
    date = models.DateField()
    class Meta:
        db_table='billing_campaign'