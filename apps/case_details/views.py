from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import Http404
from apps.customers.models import Customer
from apps.renewals.models import RenewalCase
from .serializers import CustomerSerializer
from apps.customers.models import Customer
from apps.customer_communication_preferences.models import CustomerCommunicationPreference
from .serializers import CustomerCommunicationPreferenceSerializer
from apps.renewal_timeline.models import CommonRenewalTimelineSettings
from apps.customer_payments.models import CustomerPayment
from apps.policy_timeline.models import CustomerPaymentSchedule


class CombinedPolicyDataAPIView(APIView):
    """
    API View to fetch combined policy data from multiple tables using nested serializers
    """ 
    def get(self, request, case_id=None, case_number=None):

        try:
            if case_id is None and case_number is None:
                case_id = request.query_params.get('case_id')
                case_number = request.query_params.get('case_number')
                if not case_id and not case_number:
                    return Response({
                        'success': False,
                        'message': 'case_id or case_number parameter is required',
                        'data': None
                    }, status=status.HTTP_400_BAD_REQUEST)

            if case_id:
                renewal_case = get_object_or_404(
                    RenewalCase.objects.select_related('customer', 'policy', 'policy__customer'),  
                    id=case_id
                )
            else:
                renewal_case = RenewalCase.objects.select_related('customer', 'policy', 'policy__customer').filter(case_number__iexact=case_number).first()  # type: ignore[attr-defined]
                if not renewal_case:
                    raise Http404(f"Renewal case with case_number '{case_number}' not found")

            customer_id = None
            if renewal_case.customer:
                customer_id = renewal_case.customer.id
            elif renewal_case.policy and renewal_case.policy.customer:
                customer_id = renewal_case.policy.customer.id
            else:
                raise ValueError("Customer not found for this renewal case")

            customer = get_object_or_404(
                Customer.objects.select_related(  
                    'financial_profile',
                    'channel_id'
                ).prefetch_related(
                    'customer_files',
                    'policies__agent',
                    'policies__policy_type',
                    'policies__policy_type__policy_features',
                    'policies__policy_type__policy_coverages',
                    'policies__policy_type__policy_coverages__additional_benefits',
                    'policies__exclusions'
                ),
                id=customer_id
            )

            serializer = CustomerSerializer(customer)

            return Response({
                'success': True,
                'message': 'Combined policy data retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Http404:
            return Response({
                'success': False,
                'message': 'Renewal case not found',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        except RenewalCase.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Renewal case not found',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        except Customer.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Customer not found for this renewal case',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError as ve:
            return Response({
                'success': False,
                'message': str(ve),
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving combined policy data: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# Preferences

class CustomerCommunicationPreferencesAPIView(APIView):
    def get(self, request, case_number):
        try:
            renewal_case = RenewalCase.objects.get(case_number=case_number)
            preferences = CustomerCommunicationPreference.objects.filter(case=renewal_case)
            serializer = CustomerCommunicationPreferenceSerializer(preferences, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response({"error": "Case not found"}, status=status.HTTP_404_NOT_FOUND)
        

class CustomerPreferencesSummaryAPIView(APIView):
    """Combine data from Customer, Communication Preferences, Renewal Timeline, and Payments.
    Does not change any existing logic; read-only aggregation for the Preferences page.
    """

    def get(self, request, case_id=None, case_ref=None):
        try:
            if case_id is None and case_ref is None:
                case_id = request.query_params.get('case_id')
                case_ref = request.query_params.get('case_number')
                if not case_id and not case_ref:
                    return Response({
                        'success': False,
                        'message': 'case_id or case_number parameter is required',
                        'data': None
                    }, status=status.HTTP_400_BAD_REQUEST)

            if case_ref:
                renewal_case = get_object_or_404(RenewalCase, case_number=case_ref)
            else:
                renewal_case = get_object_or_404(RenewalCase, id=case_id)
            customer = renewal_case.customer if hasattr(renewal_case, 'customer') and renewal_case.customer else renewal_case.policy.customer

            # Customer basics
            customer_info = {
                'id': customer.id,
                'customer_code': getattr(customer, 'customer_code', None),
                'name': f"{customer.first_name} {customer.last_name}".strip(),
                'email': customer.email,
                'phone': customer.phone,
                'preferred_language': getattr(customer, 'preferred_language', None),
            }

            pref_qs = CustomerCommunicationPreference.objects.filter(customer=customer).order_by('-updated_at', '-created_at')  # type: ignore[attr-defined]
            comm_pref = pref_qs.first()
            communication = None
            if comm_pref:
                communication = {
                    'preferred_channel': comm_pref.preferred_channel,
                    'email_enabled': comm_pref.email_enabled,
                    'sms_enabled': comm_pref.sms_enabled,
                    'phone_enabled': comm_pref.phone_enabled,
                    'whatsapp_enabled': comm_pref.whatsapp_enabled,
                    'postal_mail_enabled': getattr(comm_pref, 'postal_mail_enabled', False),
                    'push_notification_enabled': getattr(comm_pref, 'push_notification_enabled', False),
                    'preferred_language': getattr(comm_pref, 'preferred_language', None),
                }

            renewal_timeline = None
            common_timeline_settings = CommonRenewalTimelineSettings.objects.filter(is_active=True).first()
            # Try to get specific customer behavior
            payment_schedule, created = CustomerPaymentSchedule.objects.get_or_create(
                customer=customer,
                defaults={
                    'average_payment_timing_days': 5,
                    'preferred_payment_method': 'credit_card',
                    'total_payments_last_12_months': 12
                }
            )

            if common_timeline_settings:
                if common_timeline_settings.reminder_schedule:
                    formatted_reminder_schedule = common_timeline_settings.reminder_schedule
                else:
                    formatted_reminder_schedule = []
                    for days in common_timeline_settings.reminder_days:
                        if days == 30:
                            formatted_reminder_schedule.append("30 days before due date (Email)")
                        elif days == 14:
                            formatted_reminder_schedule.append("14 days before due date (Email)")
                        elif days == 7:
                            formatted_reminder_schedule.append("7 days before due date (Phone)")
                        else:
                            formatted_reminder_schedule.append(f"{days} days before due date (Email)")
                
                renewal_pattern = common_timeline_settings.renewal_pattern
                if payment_schedule:
                    avg_days = payment_schedule.average_payment_timing_days
                    renewal_pattern = f"Pays {abs(avg_days)} days {'early' if avg_days >= 0 else 'late'}"

                renewal_timeline = {
                    'renewal_pattern': renewal_pattern,
                    'reminder_schedule': formatted_reminder_schedule,
                    'auto_renewal_enabled': common_timeline_settings.auto_renewal_enabled,
                    'is_active': common_timeline_settings.is_active,
                    'description': common_timeline_settings.description,
                }

            payments_qs = CustomerPayment.objects.filter(renewal_case=renewal_case).order_by('-payment_date')  # type: ignore[attr-defined]
            if not payments_qs.exists():
                payments_qs = CustomerPayment.objects.filter(customer=customer).order_by('-payment_date')  # type: ignore[attr-defined]
            latest_payment = payments_qs.first()
            payment_info = None
            if latest_payment:
                payment_info = {
                    'payment_amount': str(latest_payment.payment_amount),
                    'payment_status': latest_payment.payment_status,
                    'payment_mode': latest_payment.payment_mode,
                    'payment_date': latest_payment.payment_date,
                    'transaction_id': latest_payment.transaction_id,
                }

            data = {
                'customer': customer_info,
                'communication_preferences': communication,
                'renewal_timeline': renewal_timeline,
                'latest_payment': payment_info,
            }

            return Response({
                'success': True,
                'message': 'Preferences summary retrieved successfully',
                'data': data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to fetch preferences summary: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
