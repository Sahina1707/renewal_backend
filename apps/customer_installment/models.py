from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Min, Max, Q
from apps.core.models import BaseModel
class CustomerInstallment(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("overdue", "Overdue"),
        ("paid", "Paid"),
    ]

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='installments',
        help_text="Customer reference"
    )
    renewal_case = models.ForeignKey(
        'renewals.RenewalCase',
        on_delete=models.CASCADE,
        related_name='installments',
        help_text="Renewal case reference"
    )
    period = models.CharField(max_length=50, help_text="Installment period e.g. 'March 2024'")
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Installment amount"
    )
    due_date = models.DateField(help_text="Installment due date")
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default="pending",
        help_text="Installment status"
    )

    payment = models.ForeignKey(
        'customer_payments.CustomerPayment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installments',
        help_text="Associated payment record"
    )

    class Meta:
        db_table = 'customer_installments'
        ordering = ['-due_date', '-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['renewal_case']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['period']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='positive_installment_amount'
            ),
        ]

    def mark_as_paid(self, payment):
        """Link payment and mark installment as paid"""
        self.payment = payment
        self.status = "paid"
        self.save()

    def days_overdue(self):
        """Calculate days overdue for an installment"""
        if self.status in ['pending', 'overdue'] and self.due_date < timezone.now().date():
            today = timezone.now().date()
            return (today - self.due_date).days
        return 0

    def is_overdue(self):
        """Check if installment is overdue"""
        return self.days_overdue() > 0

    def update_status_based_on_due_date(self):
        """Automatically update status based on due date"""
        if self.status == 'pending' and self.is_overdue():
            self.status = 'overdue'
            self.save(update_fields=['status'])

    @classmethod
    def get_outstanding_installments(cls, customer_id=None, case_id=None):
        """Get all outstanding installments (pending + overdue)"""
        from django.db import models
        queryset = cls.objects.filter(
            Q(status='pending') | Q(status='overdue')
        )
        
        if customer_id:
            queryset = queryset.filter(customer=customer_id)
        if case_id:
            queryset = queryset.filter(renewal_case_id=case_id)
        
        return queryset

    @classmethod
    def get_outstanding_summary(cls, customer_id=None, case_id=None):
        """Get outstanding amounts summary statistics"""
        outstanding = cls.get_outstanding_installments(customer_id, case_id)
        
        if not outstanding.exists():
            return {
                'total_outstanding': 0,
                'total_installments': 0,
                'oldest_due_date': None,
                'latest_due_date': None,
                'average_amount': 0,
                'pending_count': 0,
                'overdue_count': 0
            }
        
        summary = outstanding.aggregate(
            total_outstanding=Sum('amount'),
            total_installments=Count('id'),
            oldest_due_date=Min('due_date'),
            latest_due_date=Max('due_date'),
            average_amount=Avg('amount')
        )
        
        summary['pending_count'] = outstanding.filter(status='pending').count()
        summary['overdue_count'] = outstanding.filter(status='overdue').count()
        
        return summary

    def __str__(self):
        return f"{self.period} - {self.amount} ({self.status})"