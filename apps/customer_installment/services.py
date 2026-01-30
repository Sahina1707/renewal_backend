from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from .models import CustomerInstallment
class InstallmentIntegrationService:
    """Service class for integrating installments with policy and payment systems"""
    
    @staticmethod
    def create_installments_for_policy(policy, renewal_case=None):
        try:
            with transaction.atomic():
                installments_created = []
                
                if policy.payment_frequency == 'monthly':
                    installments_created = InstallmentIntegrationService._create_monthly_installments(
                        policy, renewal_case
                    )
                elif policy.payment_frequency == 'quarterly':
                    installments_created = InstallmentIntegrationService._create_quarterly_installments(
                        policy, renewal_case
                    )
                elif policy.payment_frequency == 'yearly':
                    installments_created = InstallmentIntegrationService._create_yearly_installments(
                        policy, renewal_case
                    )
                elif policy.payment_frequency == 'single':
                    installments_created = InstallmentIntegrationService._create_single_installment(
                        policy, renewal_case
                    )
                
                return {
                    'success': True,
                    'installments_created': len(installments_created),
                    'installments': installments_created
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'installments_created': 0
            }
    
    @staticmethod
    def _create_monthly_installments(policy, renewal_case):
        """Create monthly installments for a policy"""
        installments = []
        monthly_amount = policy.premium_amount / 12
        
        for month in range(1, 13):
            due_date = policy.start_date + timedelta(days=30 * month)
            
            installment = CustomerInstallment.objects.create(
                customer=policy.customer,
                renewal_case=renewal_case,
                period=f"{month:02d}/{policy.start_date.year}",
                amount=monthly_amount,
                due_date=due_date,
                status='pending'
            )
            installments.append(installment)
        
        return installments
    
    @staticmethod
    def _create_quarterly_installments(policy, renewal_case):
        """Create quarterly installments for a policy"""
        installments = []
        quarterly_amount = policy.premium_amount / 4
        
        for quarter in range(1, 5):
            due_date = policy.start_date + timedelta(days=90 * quarter)
            
            installment = CustomerInstallment.objects.create(
                customer=policy.customer,
                renewal_case=renewal_case,
                period=f"Q{quarter}/{policy.start_date.year}",
                amount=quarterly_amount,
                due_date=due_date,
                status='pending'
            )
            installments.append(installment)
        
        return installments
    
    @staticmethod
    def _create_yearly_installments(policy, renewal_case):
        """Create yearly installments for a policy"""
        installments = []
        
        installment = CustomerInstallment.objects.create(
            customer=policy.customer,
            renewal_case=renewal_case,
            period=f"Year 1/{policy.start_date.year}",
            amount=policy.premium_amount,
            due_date=policy.start_date,
            status='pending'
        )
        installments.append(installment)
        
        return installments
    
    @staticmethod
    def _create_single_installment(policy, renewal_case):
        """Create single installment for one-time payment"""
        installments = []
        
        installment = CustomerInstallment.objects.create(
            customer=policy.customer,
            renewal_case=renewal_case,
            period=f"Single Payment/{policy.start_date.year}",
            amount=policy.premium_amount,
            due_date=policy.start_date,
            status='pending'
        )
        installments.append(installment)
        
        return installments
    
    @staticmethod
    def link_payment_to_installment(payment):
        try:
            installment = InstallmentIntegrationService._find_matching_installment(payment)
            
            if installment:
                installment.mark_as_paid(payment)
                return {
                    'success': True,
                    'installment_id': installment.id,
                    'message': f'Payment linked to installment {installment.period}'
                }
            else:
                return {
                    'success': False,
                    'message': 'No matching installment found for this payment'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _find_matching_installment(payment):
        """Find the most appropriate installment for a payment"""
        if hasattr(payment, 'renewal_case') and payment.renewal_case:
            installment = CustomerInstallment.objects.filter(
                customer=payment.customer,
                renewal_case=payment.renewal_case,
                status='pending'
            ).order_by('due_date').first()
            
            if installment:
                return installment
        
        if payment.payment_amount:
            installment = CustomerInstallment.objects.filter(
                customer=payment.customer,
                status='pending',
                amount=payment.payment_amount
            ).order_by('due_date').first()
            
            if installment:
                return installment
        
        installment = CustomerInstallment.objects.filter(
            customer=payment.customer,
            status='pending'
        ).order_by('due_date').first()
        
        return installment
    
    @staticmethod
    def update_overdue_installments():
        try:
            updated_count = 0
            pending_installments = CustomerInstallment.objects.filter(status='pending')
            
            for installment in pending_installments:
                if installment.is_overdue():
                    installment.status = 'overdue'
                    installment.save(update_fields=['status'])
                    updated_count += 1
            
            return {
                'success': True,
                'updated_count': updated_count,
                'message': f'Updated {updated_count} installments to overdue status'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'updated_count': 0
            }