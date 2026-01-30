from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import BaseModel
from apps.customers.models import Customer
class CustomerPayment(BaseModel):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partial', 'Partial Payment'),
        ('overdue', 'Overdue'),
    ]
    
    PAYMENT_MODE_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('net_banking', 'Net Banking'),
        ('upi', 'UPI'),
        ('wallet', 'Digital Wallet'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('emi', 'EMI'),
        ('auto_debit', 'Auto Debit'),
    ]
    
    # Foreign Keys
    customer = models.ForeignKey(
            Customer,
            on_delete=models.CASCADE,
            related_name="payments",
            null=True,
            blank=True
        )

    renewal_case = models.ForeignKey(
        "renewals.RenewalCase",
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True
    )

    # Payment Details
    payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Payment amount"
    )
    
    payment_status = models.CharField(
        max_length=50,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        help_text="Current status of the payment"
    )
    
    payment_date = models.DateTimeField(
        help_text="Date and time when payment was made"
    )
    
    payment_mode = models.CharField(
        max_length=50,
        choices=PAYMENT_MODE_CHOICES,
        help_text="Mode of payment used"
    )
    
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique transaction identifier"
    )
    
    # Additional Payment Information
    gateway_response = models.TextField(
        blank=True,
        help_text="Payment gateway response details"
    )
    
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bank or gateway reference number"
    )
    
    payment_gateway = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment gateway used (Razorpay, PayU, etc.)"
    )
    
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Currency code (INR, USD, etc.)"
    )
    
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('1.0000'),
        help_text="Exchange rate if payment in foreign currency"
    )
    
    # Fee and Tax Information
    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Processing fee charged"
    )
    
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Tax amount on the payment"
    )
    
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Discount amount applied"
    )
    
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Net amount after fees and taxes"
    )
    
    # Payment Attempt Information
    attempt_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of payment attempts"
    )
    
    is_auto_payment = models.BooleanField(
        default=False,
        help_text="Whether this was an automatic payment"
    )
    
    # Failure Information
    failure_reason = models.TextField(
        blank=True,
        help_text="Reason for payment failure"
    )
    
    failure_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment gateway failure code"
    )
    
    # Refund Information
    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount refunded"
    )
    
    refund_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when refund was processed"
    )
    
    refund_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Refund transaction reference"
    )
    
    # Receipt Information
    receipt_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Receipt number for the payment"
    )
    
    receipt_url = models.URLField(
        blank=True,
        help_text="URL to download payment receipt"
    )
    
    # Due Date Information
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Payment due date"
    )
    
    grace_period_days = models.PositiveIntegerField(
        default=0,
        help_text="Grace period in days after due date"
    )
    
    # Notes and Comments
    payment_notes = models.TextField(
        blank=True,
        help_text="Additional notes about the payment"
    )
    
    customer_remarks = models.TextField(
        blank=True,
        help_text="Customer remarks or special instructions"
    )
    
    class Meta:
        db_table = 'customer_payments'
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['payment_status']),
            models.Index(fields=['payment_mode']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['payment_gateway']),
            models.Index(fields=['due_date']),
            models.Index(fields=['is_auto_payment']),
            models.Index(fields=['currency']),
            models.Index(fields=['receipt_number']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(payment_amount__gt=0),
                name='positive_payment_amount'
            ),
            models.CheckConstraint(
                check=models.Q(net_amount__gte=0),
                name='non_negative_net_amount'
            ),
            models.CheckConstraint(
                check=models.Q(refund_amount__gte=0),
                name='non_negative_refund_amount'
            ),
        ]
   
    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if not self.due_date:
            return False
        
        from django.utils import timezone
        today = timezone.now().date()
        grace_end_date = self.due_date + timezone.timedelta(days=self.grace_period_days)
        
        return (
            today > grace_end_date and 
            self.payment_status in ['pending', 'failed']
        )
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        
        from django.utils import timezone
        today = timezone.now().date()
        grace_end_date = self.due_date + timezone.timedelta(days=self.grace_period_days)
        
        return (today - grace_end_date).days
    
    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.payment_status == 'completed'
    
    @property
    def is_failed(self):
        """Check if payment failed"""
        return self.payment_status in ['failed', 'cancelled']
    
    @property
    def is_pending(self):
        """Check if payment is pending"""
        return self.payment_status in ['pending', 'processing']
    
    @property
    def is_refunded(self):
        """Check if payment was refunded"""
        return self.payment_status == 'refunded' or self.refund_amount > 0
    
    @property
    def total_amount_with_fees(self):
        """Calculate total amount including fees and taxes"""
        return self.payment_amount + self.processing_fee + self.tax_amount
    
    @property
    def effective_amount(self):
        """Calculate effective amount after discount"""
        return self.payment_amount - self.discount_amount
    
    @property
    def payment_summary(self):
        """Get payment summary"""
        return f"{self.get_payment_mode_display()} - {self.get_payment_status_display()} - ₹{self.payment_amount}"
    
    @property
    def transaction_summary(self):
        """Get transaction summary"""
        parts = []
        parts.append(f"TXN: {self.transaction_id}")
        if self.reference_number:
            parts.append(f"REF: {self.reference_number}")
        if self.payment_gateway:
            parts.append(f"Gateway: {self.payment_gateway}")
        return " | ".join(parts)
    
    def calculate_net_amount(self):
        """Calculate and update net amount"""
        self.net_amount = (
            self.payment_amount + 
            self.processing_fee + 
            self.tax_amount - 
            self.discount_amount
        )
        return self.net_amount
    
    def mark_as_completed(self, transaction_id=None, reference_number=None):
        """Mark payment as completed"""
        self.payment_status = 'completed'
        if transaction_id:
            self.transaction_id = transaction_id
        if reference_number:
            self.reference_number = reference_number
        self.save()
    
    def mark_as_failed(self, failure_reason=None, failure_code=None):
        """Mark payment as failed"""
        self.payment_status = 'failed'
        if failure_reason:
            self.failure_reason = failure_reason
        if failure_code:
            self.failure_code = failure_code
        self.save()
    
    def process_refund(self, refund_amount, refund_reference=None):
        """Process refund for the payment"""
        from django.utils import timezone
        
        if refund_amount > self.payment_amount:
            raise ValueError("Refund amount cannot exceed payment amount")
        
        self.refund_amount = refund_amount
        self.refund_date = timezone.now()
        if refund_reference:
            self.refund_reference = refund_reference
        
        if refund_amount == self.payment_amount:
            self.payment_status = 'refunded'
        else:
            self.payment_status = 'partial'
        
        self.save()
    
    def generate_receipt_number(self):
        """Generate receipt number"""
        if not self.receipt_number:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            self.receipt_number = f"RCP-{date_str}-{self.id:06d}"
            self.save()
        return self.receipt_number
