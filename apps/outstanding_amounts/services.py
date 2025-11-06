from django.db.models import Sum, Count, Avg, Min, Max, Q
from django.utils import timezone
from decimal import Decimal
from datetime import date
from apps.renewals.models import RenewalCase
from apps.customer_installment.models import CustomerInstallment
from apps.customer_payment_schedule.models import PaymentSchedule
from apps.customer_payments.models import CustomerPayment


class OutstandingAmountsService:
    """
    Service class to calculate and manage outstanding amounts for renewal cases
    """
    
    @staticmethod
    def calculate_outstanding_for_case(case_id):
        try:
            renewal_case = RenewalCase.objects.get(id=case_id)
            
            if renewal_case.status in ['renewed', 'completed']:
                return {
                    'total_outstanding': 0,
                    'oldest_due_date': None,
                    'latest_due_date': None,
                    'average_amount': 0,
                    'pending_count': 0,
                    'overdue_count': 0,
                    'installments': []
                }
            
            outstanding_installments = CustomerInstallment.objects.filter(
                renewal_case=renewal_case,
                status__in=['pending', 'overdue']
            ).order_by('due_date')
            
            outstanding_schedules = PaymentSchedule.objects.filter(
                renewal_case=renewal_case,
                status__in=['pending', 'overdue', 'failed']
            ).order_by('due_date')
            
            all_outstanding = []
            
            for installment in outstanding_installments:
                days_overdue = OutstandingAmountsService._calculate_days_overdue(installment.due_date)
                status = 'overdue' if days_overdue > 0 else 'pending'
                
                all_outstanding.append({
                    'id': installment.id,
                    'type': 'installment',
                    'period': installment.period,
                    'amount': float(installment.amount),
                    'due_date': installment.due_date,
                    'days_overdue': days_overdue,
                    'status': status,
                    'description': OutstandingAmountsService._generate_description(installment.period, 'installment')
                })
            
            for schedule in outstanding_schedules:
                days_overdue = OutstandingAmountsService._calculate_days_overdue(schedule.due_date)
                status = 'overdue' if days_overdue > 0 else 'pending'
                
                all_outstanding.append({
                    'id': schedule.id,
                    'type': 'schedule',
                    'period': OutstandingAmountsService._generate_period_from_schedule(schedule),
                    'amount': float(schedule.amount_due),
                    'due_date': schedule.due_date,
                    'days_overdue': days_overdue,
                    'status': status,
                    'description': OutstandingAmountsService._generate_description_from_schedule(schedule)
                })
            
            if all_outstanding:
                total_outstanding = sum(item['amount'] for item in all_outstanding)
                oldest_due_date = min(item['due_date'] for item in all_outstanding)
                latest_due_date = max(item['due_date'] for item in all_outstanding)
                average_amount = total_outstanding / len(all_outstanding)
                pending_count = sum(1 for item in all_outstanding if item['status'] == 'pending')
                overdue_count = sum(1 for item in all_outstanding if item['status'] == 'overdue')
            else:
                total_outstanding = 0
                oldest_due_date = None
                latest_due_date = None
                average_amount = 0
                pending_count = 0
                overdue_count = 0
            
            return {
                'total_outstanding': total_outstanding,
                'oldest_due_date': oldest_due_date,
                'latest_due_date': latest_due_date,
                'average_amount': round(average_amount, 2),
                'pending_count': pending_count,
                'overdue_count': overdue_count,
                'installments': all_outstanding
            }
            
        except RenewalCase.DoesNotExist:
            return None
        except Exception as e:
            raise Exception(f"Error calculating outstanding amounts: {str(e)}")
    
    @staticmethod
    def get_outstanding_summary(case_id):
        return OutstandingAmountsService.calculate_outstanding_for_case(case_id)
    
    @staticmethod
    def initiate_payment_for_case(case_id, installment_ids=None, payment_data=None):
        try:
            renewal_case = RenewalCase.objects.get(id=case_id)
            
            if installment_ids:
                installments_to_pay = CustomerInstallment.objects.filter(
                    id__in=installment_ids,
                    renewal_case=renewal_case,
                    status__in=['pending', 'overdue']
                )
            else:
                installments_to_pay = CustomerInstallment.objects.filter(
                    renewal_case=renewal_case,
                    status__in=['pending', 'overdue']
                )
            
            if not installments_to_pay.exists():
                return {
                    'success': False,
                    'message': 'No outstanding installments found to pay'
                }
            
            total_amount = sum(inst.amount for inst in installments_to_pay)
            
            payment = CustomerPayment.objects.create(
                customer=renewal_case.customer,
                renewal_case=renewal_case,
                payment_amount=total_amount,
                payment_status='processing',
                payment_date=timezone.now(),
                payment_mode=payment_data.get('payment_mode', 'upi'),
                transaction_id=OutstandingAmountsService._generate_transaction_id(),
                due_date=timezone.now().date(),
                payment_notes=f"Payment for {len(installments_to_pay)} outstanding installments"
            )
            
            for installment in installments_to_pay:
                installment.mark_as_paid(payment)
            
            return {
                'success': True,
                'message': f'Payment initiated for {len(installments_to_pay)} installments',
                'payment_id': payment.id,
                'transaction_id': payment.transaction_id,
                'total_amount': float(total_amount)
            }
            
        except RenewalCase.DoesNotExist:
            return {
                'success': False,
                'message': 'Renewal case not found'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error initiating payment: {str(e)}'
            }
    
    @staticmethod
    def setup_payment_plan_for_case(case_id, plan_data):
        try:
            renewal_case = RenewalCase.objects.get(id=case_id)
            
            outstanding_summary = OutstandingAmountsService.get_outstanding_summary(case_id)
            total_outstanding = outstanding_summary['total_outstanding']
            
            if total_outstanding <= 0:
                return {
                    'success': False,
                    'message': 'No outstanding amounts to create payment plan for'
                }
            
            installment_count = plan_data.get('installment_count', 3)
            start_date = plan_data.get('start_date', timezone.now().date())
            payment_frequency = plan_data.get('payment_frequency', 'monthly')
            
            installment_amount = total_outstanding / installment_count
            
            created_schedules = []
            current_date = start_date
            
            for i in range(installment_count):
                if payment_frequency == 'monthly':
                    from dateutil.relativedelta import relativedelta
                    next_date = current_date + relativedelta(months=1)
                elif payment_frequency == 'quarterly':
                    from dateutil.relativedelta import relativedelta
                    next_date = current_date + relativedelta(months=3)
                else:  
                    from datetime import timedelta
                    next_date = current_date + timedelta(weeks=1)
                
                schedule = PaymentSchedule.objects.create(
                    renewal_case=renewal_case,
                    due_date=next_date,
                    amount_due=installment_amount,
                    status='scheduled',
                    payment_method=plan_data.get('payment_method', 'auto_debit'),
                    installment_number=i + 1,
                    total_installments=installment_count,
                    description=f"Payment plan installment {i + 1}/{installment_count}",
                    auto_payment_enabled=plan_data.get('auto_payment_enabled', True)
                )
                
                created_schedules.append(schedule)
                current_date = next_date
            
            return {
                'success': True,
                'message': f'Payment plan created with {installment_count} installments',
                'total_amount': float(total_outstanding),
                'installment_amount': float(installment_amount),
                'installment_count': installment_count,
                'payment_frequency': payment_frequency,
                'schedules_created': len(created_schedules)
            }
            
        except RenewalCase.DoesNotExist:
            return {
                'success': False,
                'message': 'Renewal case not found'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error setting up payment plan: {str(e)}'
            }
    
    @staticmethod
    def _calculate_days_overdue(due_date):
        """Calculate days overdue from due date"""
        if not due_date:
            return 0
        
        today = date.today()
        if due_date >= today:
            return 0
        
        return (today - due_date).days
    
    @staticmethod
    def _generate_description(period, item_type):
        """Generate description for installment"""
        if item_type == 'installment':
            return f"Quarterly premium for family health insurance - {period}"
        return f"Payment for {period}"
    
    @staticmethod
    def _generate_period_from_schedule(schedule):
        """Generate period string from payment schedule"""
        if schedule.installment_number and schedule.total_installments:
            return f"Installment {schedule.installment_number}/{schedule.total_installments}"
        return f"Payment {schedule.id}"
    
    @staticmethod
    def _generate_description_from_schedule(schedule):
        """Generate description from payment schedule"""
        if schedule.description:
            return schedule.description
        return f"Payment schedule installment {schedule.installment_number}"
    
    @staticmethod
    def _generate_transaction_id():
        """Generate unique transaction ID"""
        import uuid
        return f"TXN_{uuid.uuid4().hex[:12].upper()}"
