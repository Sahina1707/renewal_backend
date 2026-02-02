from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import BaseModel
from apps.renewals.models import RenewalCase
class PaymentSchedule(BaseModel):
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue'),
        ('partial', 'Partial Payment'),
        ('rescheduled', 'Rescheduled'),
        ('skipped', 'Skipped'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
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
        ('standing_instruction', 'Standing Instruction'),
        ('nach', 'NACH'),
        ('enach', 'E-NACH'),
    ]
    
    renewal_case = models.ForeignKey(
        RenewalCase,
        on_delete=models.CASCADE,
        related_name='payment_schedules',
        help_text="Renewal case this payment schedule belongs to"
    )
    
    due_date = models.DateField(
        help_text="Date when payment is due"
    )
    
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount due for this scheduled payment"
    )
    
    status = models.CharField(
        max_length=100,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        help_text="Current status of the scheduled payment"
    )
    
    payment_method = models.CharField(
        max_length=100,
        choices=PAYMENT_METHOD_CHOICES,
        help_text="Preferred payment method for this schedule"
    )
    
    installment_number = models.PositiveIntegerField(
        default=1,
        help_text="Installment number in the payment series"
    )
    
    total_installments = models.PositiveIntegerField(
        default=1,
        help_text="Total number of installments planned"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description or notes about this payment schedule"
    )
    
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether reminder has been sent for this payment"
    )
    
    reminder_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when reminder should be sent"
    )
    
    reminder_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of reminders sent"
    )
    
    auto_payment_enabled = models.BooleanField(
        default=False,
        help_text="Whether auto payment is enabled for this schedule"
    )
    
    auto_payment_method = models.CharField(
        max_length=100,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        help_text="Auto payment method if enabled"
    )
    
    payment_gateway = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment gateway to be used"
    )
    
    gateway_schedule_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Gateway-specific schedule ID"
    )
    
    grace_period_days = models.PositiveIntegerField(
        default=0,
        help_text="Grace period in days after due date"
    )
    
    late_fee_applicable = models.BooleanField(
        default=False,
        help_text="Whether late fee is applicable"
    )
    
    late_fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Late fee amount if payment is overdue"
    )
    
    late_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Late fee percentage of amount due"
    )
    
    early_payment_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Discount for early payment"
    )
    
    early_payment_days = models.PositiveIntegerField(
        default=0,
        help_text="Days before due date for early payment discount"
    )
    
    processed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when payment was processed"
    )
    
    processed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount actually processed"
    )
    
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Transaction reference from payment gateway"
    )
    
    failure_reason = models.TextField(
        blank=True,
        help_text="Reason for payment failure"
    )
    
    failure_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment gateway failure code"
    )
    
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    
    max_retry_attempts = models.PositiveIntegerField(
        default=3,
        help_text="Maximum retry attempts allowed"
    )
    
    next_retry_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next retry attempt date"
    )
    
    original_due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Original due date before rescheduling"
    )
    
    reschedule_reason = models.TextField(
        blank=True,
        help_text="Reason for rescheduling payment"
    )
    
    reschedule_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times payment has been rescheduled"
    )
    
    customer_notified = models.BooleanField(
        default=False,
        help_text="Whether customer has been notified about this schedule"
    )
    
    notification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when customer was notified"
    )
    
    customer_acknowledgment = models.BooleanField(
        default=False,
        help_text="Whether customer has acknowledged the schedule"
    )
    
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal notes for staff"
    )
    
    customer_notes = models.TextField(
        blank=True,
        help_text="Notes from customer"
    )
    
    class Meta:
        db_table = 'payment_schedule'
        ordering = ['due_date', 'installment_number']
        indexes = [
            models.Index(fields=['renewal_case']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['auto_payment_enabled']),
            models.Index(fields=['reminder_date']),
            models.Index(fields=['processed_date']),
            models.Index(fields=['installment_number']),
            models.Index(fields=['payment_gateway']),
            models.Index(fields=['gateway_schedule_id']),
            models.Index(fields=['late_fee_applicable']),
            models.Index(fields=['next_retry_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_due__gt=0),
                name='positive_amount_due'
            ),
            models.CheckConstraint(
                check=models.Q(processed_amount__gte=0),
                name='non_negative_processed_amount'
            ),
            models.CheckConstraint(
                check=models.Q(late_fee_amount__gte=0),
                name='non_negative_late_fee_amount'
            ),
            models.CheckConstraint(
                check=models.Q(early_payment_discount__gte=0),
                name='non_negative_early_payment_discount'
            ),
            models.CheckConstraint(
                check=models.Q(installment_number__gte=1),
                name='positive_installment_number'
            ),
            models.CheckConstraint(
                check=models.Q(total_installments__gte=1),
                name='positive_total_installments'
            ),
            models.CheckConstraint(
                check=models.Q(installment_number__lte=models.F('total_installments')),
                name='installment_number_within_total'
            ),
        ]
    
    def __str__(self):
        return f"Payment Schedule {self.installment_number}/{self.total_installments} - {self.renewal_case.case_number} - ₹{self.amount_due} due on {self.due_date}"
    
    @property
    def customer(self):
        """Get customer from renewal case"""
        return self.renewal_case.customer if self.renewal_case else None
    
    @property
    def customer_name(self):
        """Get customer name"""
        return self.customer.full_name if self.customer else "Unknown"
    
    @property
    def policy_number(self):
        """Get policy number from renewal case"""
        return self.renewal_case.policy.policy_number if self.renewal_case and self.renewal_case.policy else "Unknown"
    
    @property
    def case_number(self):
        """Get case number from renewal case"""
        return self.renewal_case.case_number if self.renewal_case else "Unknown"
    
    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        from django.utils import timezone
        today = timezone.now().date()
        grace_end_date = self.due_date + timezone.timedelta(days=self.grace_period_days)
        
        return (
            today > grace_end_date and 
            self.status in ['pending', 'scheduled', 'failed']
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
    def is_due_today(self):
        """Check if payment is due today"""
        from django.utils import timezone
        return self.due_date == timezone.now().date()
    
    @property
    def days_until_due(self):
        """Calculate days until due date"""
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.due_date < today:
            return 0
        
        return (self.due_date - today).days
    
    @property
    def is_eligible_for_early_discount(self):
        """Check if eligible for early payment discount"""
        if self.early_payment_discount <= 0 or self.early_payment_days <= 0:
            return False
        
        from django.utils import timezone
        today = timezone.now().date()
        early_payment_deadline = self.due_date - timezone.timedelta(days=self.early_payment_days)
        
        return today <= early_payment_deadline
    
    @property
    def applicable_late_fee(self):
        """Calculate applicable late fee"""
        if not self.late_fee_applicable or not self.is_overdue:
            return Decimal('0.00')
        
        if self.late_fee_percentage > 0:
            return (self.amount_due * self.late_fee_percentage / 100).quantize(Decimal('0.01'))
        
        return self.late_fee_amount
    
    @property
    def total_amount_due(self):
        """Calculate total amount due including late fees"""
        return self.amount_due + self.applicable_late_fee
    
    @property
    def discounted_amount(self):
        """Calculate amount after early payment discount"""
        if self.is_eligible_for_early_discount:
            return self.amount_due - self.early_payment_discount
        return self.amount_due
    
    @property
    def remaining_amount(self):
        """Calculate remaining amount to be paid"""
        return max(Decimal('0.00'), self.amount_due - self.processed_amount)
    
    @property
    def is_fully_paid(self):
        """Check if payment is fully completed"""
        return self.processed_amount >= self.amount_due and self.status == 'completed'
    
    @property
    def is_partially_paid(self):
        """Check if payment is partially completed"""
        return self.processed_amount > 0 and self.processed_amount < self.amount_due
    
    @property
    def payment_progress_percentage(self):
        """Calculate payment progress percentage"""
        if self.amount_due <= 0:
            return 0
        
        progress = (self.processed_amount / self.amount_due * 100).quantize(Decimal('0.01'))
        return min(progress, Decimal('100.00'))
    
    @property
    def can_retry(self):
        """Check if payment can be retried"""
        return (
            self.status in ['failed', 'pending'] and
            self.retry_count < self.max_retry_attempts
        )
    
    @property
    def schedule_summary(self):
        """Get schedule summary"""
        return f"Installment {self.installment_number}/{self.total_installments} - ₹{self.amount_due} due {self.due_date}"
    
    @property
    def status_display(self):
        """Get formatted status display"""
        status_map = {
            'pending': '⏳ Pending',
            'scheduled': '📅 Scheduled',
            'processing': '⚡ Processing',
            'completed': '✅ Completed',
            'failed': '❌ Failed',
            'cancelled': '🚫 Cancelled',
            'overdue': '⚠️ Overdue',
            'partial': '🔄 Partial',
            'rescheduled': '📆 Rescheduled',
            'skipped': '⏭️ Skipped',
        }
        return status_map.get(self.status, self.status.title())
    
    def mark_as_completed(self, processed_amount=None, transaction_reference=None):
        """Mark payment schedule as completed"""
        from django.utils import timezone
        
        self.status = 'completed'
        self.processed_date = timezone.now()
        
        if processed_amount is not None:
            self.processed_amount = processed_amount
        else:
            self.processed_amount = self.amount_due
        
        if transaction_reference:
            self.transaction_reference = transaction_reference
        
        self.save()
    
    def mark_as_failed(self, failure_reason=None, failure_code=None):
        """Mark payment schedule as failed"""
        self.status = 'failed'
        
        if failure_reason:
            self.failure_reason = failure_reason
        
        if failure_code:
            self.failure_code = failure_code
        
        self.retry_count += 1
        
        if self.can_retry:
            from django.utils import timezone
            self.next_retry_date = timezone.now() + timezone.timedelta(days=1)
        
        self.save()
    
    def reschedule_payment(self, new_due_date, reason=None):
        """Reschedule payment to new due date"""
        if not self.original_due_date:
            self.original_due_date = self.due_date
        
        self.due_date = new_due_date
        self.status = 'rescheduled'
        self.reschedule_count += 1
        
        if reason:
            self.reschedule_reason = reason
        
        self.save()
    
    def send_reminder(self):
        """Mark reminder as sent"""
        from django.utils import timezone
        
        self.reminder_sent = True
        self.reminder_count += 1
        self.reminder_date = timezone.now().date()
        self.save()
    
    def enable_auto_payment(self, payment_method, gateway=None, gateway_schedule_id=None):
        """Enable auto payment for this schedule"""
        self.auto_payment_enabled = True
        self.auto_payment_method = payment_method
        
        if gateway:
            self.payment_gateway = gateway
        
        if gateway_schedule_id:
            self.gateway_schedule_id = gateway_schedule_id
        
        self.save()
    
    def disable_auto_payment(self):
        """Disable auto payment for this schedule"""
        self.auto_payment_enabled = False
        self.auto_payment_method = ''
        self.gateway_schedule_id = ''
        self.save()
    
    def process_partial_payment(self, amount, transaction_reference=None):
        """Process partial payment"""
        from django.utils import timezone
        
        self.processed_amount += amount
        self.processed_date = timezone.now()
        
        if transaction_reference:
            self.transaction_reference = transaction_reference
        
        if self.processed_amount >= self.amount_due:
            self.status = 'completed'
        else:
            self.status = 'partial'
        
        self.save()
    
    def calculate_installment_amount(self, total_amount, installment_count):
        """Calculate amount for each installment"""
        if installment_count <= 0:
            return Decimal('0.00')
        
        return (total_amount / installment_count).quantize(Decimal('0.01'))
    
    def notify_customer(self):
        """Mark customer as notified"""
        from django.utils import timezone
        
        self.customer_notified = True
        self.notification_date = timezone.now()
        self.save()
