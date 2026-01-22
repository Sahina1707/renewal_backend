from django.db import models
from django.utils import timezone
from apps.customers.models import Customer
from apps.renewals.models import RenewalCase
from apps.clients.models import Client


# -------------------------
# 1. SETTINGS (Singleton)
# -------------------------
class DNCSettings(models.Model):
    enable_checking = models.BooleanField(default=True)
    block_contacts = models.BooleanField(default=True)
    auto_check = models.BooleanField(default=True)
    allow_overrides = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# -------------------------
# 2. DNC REGISTRY (MAIN)
# -------------------------
class DNCRegistry(models.Model):

    TYPE_CHOICES = [
        ('Phone Only', 'Phone Only'),
        ('Email Only', 'Email Only'),
        ('Both Phone & Email', 'Both Phone & Email'),
    ]

    SOURCE_CHOICES = [
        ('Customer Request', 'Customer Request'),
        ('Government Registry', 'Government Registry'),
        ('Manual Entry', 'Manual Entry'),
        ('System Generated', 'System Generated'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dnc_entries'
    )

    renewal_case = models.ForeignKey(
        RenewalCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dnc_records'
    )

    # ✅ REAL CLIENT CONNECTION
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dnc_entries'
    )

    customer_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    email_address = models.EmailField(blank=True, null=True)

    dnc_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')

    effective_date = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateTimeField(null=True, blank=True)

    allow_override_requests = models.BooleanField(default=False)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        # Snapshot customer data
        if self.customer:
            self.customer_name = self.customer_name or (
                getattr(self.customer, 'name', None)
                or f"{self.customer.first_name} {self.customer.last_name}"
            )
            self.phone_number = self.phone_number or getattr(self.customer, 'phone', '')
            self.email_address = self.email_address or getattr(self.customer, 'email', '')

        # Policy → Client
        if not self.client and self.renewal_case and self.renewal_case.distribution_channel:
            self.client = self.renewal_case.distribution_channel

        # No policy → random client
        if not self.client:
            self.client = Client.objects.filter(
                is_active=True,
                is_deleted=False
            ).order_by('?').first()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_name} ({self.status})"


# -------------------------
# 3. OVERRIDE HISTORY
# -------------------------
class DNCOverrideLog(models.Model):
    dnc_entry = models.ForeignKey(
        DNCRegistry,
        on_delete=models.CASCADE,
        related_name='overrides'
    )
    override_type = models.CharField(max_length=50)
    end_date = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    authorized_by = models.CharField(max_length=100, default="System User")
    created_at = models.DateTimeField(auto_now_add=True)  # ✅ FIXED

    def __str__(self):
        return f"Override for {self.dnc_entry.customer_name}"
