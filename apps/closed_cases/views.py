from rest_framework import viewsets, permissions, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from apps.renewals.models import RenewalCase
from apps.customers.models import Customer
from apps.core.pagination import StandardResultsSetPagination
from .serializers import ClosedCasesListSerializer, ClosedCasesDetailSerializer
from datetime import datetime, timedelta
from django.utils import timezone
from apps.files_upload.models import FileUpload
from apps.outstanding_amounts.services import OutstandingAmountsService
from apps.outstanding_amounts.serializers import OutstandingAmountsSummarySerializer
from apps.customer_insights.services import CustomerInsightsService
from apps.customer_insights.serializers import CustomerInsightsResponseSerializer, CommunicationHistoryResponseSerializer, ClaimsHistoryResponseSerializer


class ClosedCasesViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    lookup_field = 'id'
    lookup_url_kwarg = 'case_id'
    
    def get_queryset(self):
        return RenewalCase.objects.filter(
            status__in=['completed', 'renewed'], 
            policy__status='active'              
        ).select_related(
            'customer',                  
            'customer__channel_id',      
            'policy',                     
            'policy__policy_type',        
            'assigned_to',                
        ).prefetch_related(
            'customer__policies',         
        ).order_by('-updated_at') 
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return ClosedCasesDetailSerializer
        return ClosedCasesListSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(case_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__company_name__icontains=search) |
                Q(policy__policy_number__icontains=search) |
                Q(customer__customer_code__icontains=search)
            )
        
        channel = request.query_params.get('channel', None)
        if channel:
            queryset = queryset.filter(customer__channel_id__name__icontains=channel)
        
        agent = request.query_params.get('agent', None)
        if agent:
            queryset = queryset.filter(
                Q(assigned_to__first_name__icontains=agent) |
                Q(assigned_to__last_name__icontains=agent) |
                Q(assigned_to__username__icontains=agent)
            )
        
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(updated_at__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(updated_at__date__lte=date_to)
            except ValueError:
                pass
        
        batch_id = request.query_params.get('batch_id', None)
        if batch_id:
            queryset = queryset.filter(batch_code__icontains=batch_id)
        
        category = request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(policy__policy_type__category__icontains=category)
        
        profile = request.query_params.get('profile', None)
        if profile:
            queryset = queryset.filter(customer__profile__icontains=profile)
        
        language = request.query_params.get('language', None)
        if language:
            queryset = queryset.filter(customer__language__icontains=language)
        
        sort_by = request.query_params.get('sort_by', '-updated_at')
        valid_sort_fields = [
            'case_number', '-case_number',
            'customer__first_name', '-customer__first_name',
            'policy__policy_number', '-policy__policy_number',
            'updated_at', '-updated_at',
            'created_at', '-created_at',
            'renewal_amount', '-renewal_amount',
            'payment_date', '-payment_date'
        ]
        
        if sort_by in valid_sort_fields:
            queryset = queryset.order_by(sort_by)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'closed_cases': serializer.data,
            'total_count': queryset.count()
        })
    
    def retrieve(self, request, case_id=None, *args, **kwargs):
        """Get detailed information for a specific closed case"""
        queryset = self.get_queryset()
        case = get_object_or_404(queryset, id=case_id)
        serializer = self.get_serializer(case)
        
        return Response({
            'closed_case': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        
        total_closed_cases = queryset.count()
        
        priority_stats = {
            'medium': {
                'label': 'Medium',
                'count': queryset.count()
            }
        }
        
        channel_stats = queryset.values(
            'customer__channel_id__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10] 
        
        agent_stats = queryset.values(
            'assigned_to__first_name',
            'assigned_to__last_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]  
        
        category_stats = queryset.values(
            'policy__policy_type__category'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_closures = queryset.filter(updated_at__gte=seven_days_ago).count()
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        monthly_closures = queryset.filter(updated_at__gte=thirty_days_ago).count()
        
        total_renewal_amount = sum(
            case.renewal_amount for case in queryset if case.renewal_amount
        )
        
        return Response({
            'total_closed_cases': total_closed_cases,
            'priority_breakdown': priority_stats,
            'channel_breakdown': list(channel_stats),
            'agent_breakdown': list(agent_stats),
            'category_breakdown': list(category_stats),
            'recent_closures_7_days': recent_closures,
            'monthly_closures_30_days': monthly_closures,
            'total_renewal_amount': total_renewal_amount,
            'generated_at': timezone.now().isoformat()
        })
    
    @action(detail=False, methods=['get'])
    def export_data(self, request):
        queryset = self.get_queryset()
        
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(case_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(policy__policy_number__icontains=search)
            )
        
        export_data = []
        for case in queryset:
            export_data.append({
                'case_number': case.case_number,
                'customer_name': case.customer.full_name if case.customer else '',
                'customer_mobile': case.customer.phone if case.customer else '',
                'customer_email': case.customer.email if case.customer else '',
                'policy_number': case.policy.policy_number if case.policy else '',
                'policy_type': case.policy.policy_type.name if case.policy and case.policy.policy_type else '',
                'category': case.policy.policy_type.category if case.policy and case.policy.policy_type else '',
                'premium_amount': str(case.policy.premium_amount) if case.policy else '',
                'renewal_amount': str(case.renewal_amount) if case.renewal_amount else '',
                'priority': case.get_priority_display(),
                'channel': case.customer.channel_id.name if case.customer and case.customer.channel_id else '',
                'agent': f"{case.assigned_to.first_name} {case.assigned_to.last_name}".strip() if case.assigned_to else '',
                'batch_id': case.batch_code,
                'closed_date': case.updated_at.strftime('%Y-%m-%d %H:%M:%S') if case.updated_at else '',
                'payment_date': case.customer_payment.payment_date.strftime('%Y-%m-%d %H:%M:%S') if case.customer_payment and case.customer_payment.payment_date else '',
                'communication_attempts': case.communication_attempts_count,
            })
        
        return Response({
            'export_data': export_data,
            'total_records': len(export_data),
            'exported_at': timezone.now().isoformat()
        })

class ClosedCasesCombinedDataAPIView(APIView):
    
    def get(self, request, case_number=None):
        try:
            if not case_number:
                return Response({
                    'success': False,
                    'message': 'case_number parameter is required',
                    'data': None
                }, status=status.HTTP_400_BAD_REQUEST)

            renewal_case = RenewalCase.objects.select_related(
                'customer', 
                'policy', 
                'policy__customer'
            ).filter(
                case_number__iexact=case_number,
                status='renewed' 
            ).first()
            
            if not renewal_case:
                return Response({
                    'success': False,
                    'message': 'Renewal case not found or case is not renewed',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

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

            from apps.case_details.serializers import CustomerSerializer
            serializer = CustomerSerializer(customer)

            return Response({
                'success': True,
                'message': 'Combined policy data retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Http404:
            return Response({
                'success': False,
                'message': 'Renewal case not found or case is not renewed',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        except RenewalCase.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Renewal case not found or case is not renewed',
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


class ClosedCasesPreferencesSummaryAPIView(APIView):
   
    def get(self, request, case_ref=None):
        try:
            if not case_ref:
                return Response({
                    'success': False,
                    'message': 'case_number parameter is required',
                    'data': None
                }, status=status.HTTP_400_BAD_REQUEST)

            renewal_case = RenewalCase.objects.filter(
                case_number__iexact=case_ref,
                status='renewed' 
            ).first()
            
            if not renewal_case:
                return Response({
                    'success': False,
                    'message': 'Renewal case not found or case is not renewed',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

            customer = renewal_case.customer if (
                hasattr(renewal_case, 'customer') and renewal_case.customer
            ) else renewal_case.policy.customer

            customer_info = {
                'id': customer.id,
                'customer_code': getattr(customer, 'customer_code', None),
                'name': f"{customer.first_name} {customer.last_name}".strip(),
                'email': customer.email,
                'phone': customer.phone,
                'preferred_language': getattr(customer, 'preferred_language', None),
            }

            from apps.customer_communication_preferences.models import CustomerCommunicationPreference
            pref_qs = CustomerCommunicationPreference.objects.filter(
                customer=customer
            ).order_by('-updated_at', '-created_at')
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

            from apps.renewal_timeline.models import CommonRenewalTimelineSettings
            renewal_timeline = None
            common_timeline_settings = CommonRenewalTimelineSettings.objects.filter(
                is_active=True
            ).first()
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
                
                renewal_timeline = {
                    'renewal_pattern': common_timeline_settings.renewal_pattern,
                    'reminder_schedule': formatted_reminder_schedule,
                    'auto_renewal_enabled': common_timeline_settings.auto_renewal_enabled,
                    'is_active': common_timeline_settings.is_active,
                    'description': common_timeline_settings.description,
                }

            from apps.customer_payments.models import CustomerPayment
            payments_qs = CustomerPayment.objects.filter(
                renewal_case=renewal_case
            ).order_by('-payment_date')
            if not payments_qs.exists():
                payments_qs = CustomerPayment.objects.filter(
                    customer=customer
                ).order_by('-payment_date')
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


class ClosedCasesPolicyMembersAPIView(APIView):
   
    def get(self, request, case_id=None):
        try:
            from apps.policies.models import PolicyMember
            from apps.policies.serializers import PolicyMemberSerializer
            
            if not case_id:
                return Response({
                    'success': False,
                    'message': 'case_id or case_number parameter is required',
                    'data': None
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                case_id_int = int(case_id)
                renewal_case = RenewalCase.objects.filter(
                    id=case_id_int,
                    status='renewed'  
                ).first()
            except ValueError:
                renewal_case = RenewalCase.objects.filter(
                    case_number__iexact=case_id,
                    status='renewed'  
                ).first()
            
            if not renewal_case:
                return Response({
                    'success': False,
                    'message': 'Renewal case not found or case is not renewed',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

            members = PolicyMember.objects.filter(renewal_case_id=renewal_case.id)
            
            serializer = PolicyMemberSerializer(members, many=True)
            
            return Response({
                'success': True,
                'message': f'Policy members retrieved successfully for case {case_id}',
                'data': serializer.data,
                'count': members.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving policy members: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClosedCasesOffersAPIView(APIView):
    
    def get(self, request, case_id=None):
        try:
            from apps.offers.models import Offer
            from apps.offers.serializers import OfferSerializer
            from apps.customer_assets.models import CustomerAssets
            
            if not case_id:
                return Response({
                    'success': False,
                    'message': 'case_id parameter is required',
                    'data': None
                }, status=status.HTTP_400_BAD_REQUEST)

            renewal_case = RenewalCase.objects.select_related(
                'customer', 
                'customer__financial_profile'
            ).filter(
                case_number__iexact=case_id,
                status='renewed' 
            ).first()
            
            if not renewal_case:
                return Response({
                    'success': False,
                    'message': 'Renewal case not found or case is not renewed',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

            customer = renewal_case.customer
            
            financial_profile = None
            annual_income = None
            try:
                financial_profile = customer.financial_profile
                if financial_profile and financial_profile.annual_income:
                    annual_income = float(financial_profile.annual_income)
            except Exception:
                pass
            
            has_assets = CustomerAssets.objects.filter(
                customer=customer,
                is_deleted=False
            ).exists()
            
            all_offers = Offer.objects.filter(is_active=True).order_by('display_order')
            
            eligible_offers = []
            
            for offer in all_offers:
                is_eligible = False
                offer_title_lower = offer.title.lower()
                offer_type = offer.offer_type
                
                if offer_title_lower == 'emi payment plan':
                    is_eligible = True
                
                elif offer_title_lower == 'quarterly payment':
                    if annual_income and annual_income > 500000:
                        is_eligible = True
                
                elif offer_title_lower == 'annual payment':
                    if annual_income and annual_income > 800000:
                        is_eligible = True
                
                elif offer_title_lower == 'premium funding':
                    if has_assets:
                        is_eligible = True
                
                elif offer_type in ['product', 'bundle']:
                    if annual_income and annual_income > 300000:
                        is_eligible = True
                
                elif offer_type in ['discount', 'special_offer']:
                    if annual_income and annual_income > 300000:
                        is_eligible = True
                
                if is_eligible:
                    eligible_offers.append(offer)
            
            serializer = OfferSerializer(eligible_offers, many=True)
            
            return Response({
                'success': True,
                'message': f'Offers retrieved successfully for case {case_id}',
                'data': serializer.data,
                'count': len(eligible_offers)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving offers: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def closed_cases_timeline_view(request, case_number):
    
    try:
        from apps.case_history.models import CaseHistory
        from apps.case_history.serializers import (
            CaseTimelineSummarySerializer,
            CaseTimelineHistorySerializer
        )
        from apps.case_logs.models import CaseLog
        from apps.case_logs.serializers import CaseLogSerializer
        
        case = RenewalCase.objects.select_related(
            'policy__agent', 
            'customer', 
            'assigned_to'
        ).filter(
            case_number__iexact=case_number,
            status='renewed',  
            is_deleted=False
        ).first()
        
        if not case:
            return Response({
                'success': False,
                'message': 'Renewal case not found or case is not renewed',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not (request.user.is_staff or 
                case.assigned_to == request.user or 
                case.created_by == request.user):
            raise PermissionDenied("You don't have permission to view this case.")
        
        history = CaseHistory.objects.filter(
            case=case, 
            is_deleted=False
        ).select_related('created_by').order_by('created_at')
        history_serializer = CaseTimelineHistorySerializer(
            history, 
            many=True, 
            context={'request': request}
        )
        
        system_events = []
        
        if case.created_at:
            case_created_exists = history.filter(action='case_created').exists()
            if not case_created_exists:
                case_created_date = case.created_at
                if hasattr(case, 'batch_code') and case.batch_code:
                    description = f"Case uploaded via bulk upload"
                else:
                    description = "Case created"
                
                system_events.append({
                    'event_type': 'Case Created',
                    'event_description': description,
                    'event_date': case_created_date.strftime('%d/%m/%Y'),
                    'event_time': case_created_date.strftime('%H:%M:%S'),
                    'performed_by': 'System',
                    'created_at': case_created_date
                })
        
        if case.created_at:
            validation_exists = history.filter(action='validation').exists()
            if not validation_exists:
                validation_date = case.created_at + timedelta(seconds=5)
                system_events.append({
                    'event_type': 'Validation',
                    'event_description': 'All required fields present and valid',
                    'event_date': validation_date.strftime('%d/%m/%Y'),
                    'event_time': validation_date.strftime('%H:%M:%S'),
                    'performed_by': 'System',
                    'created_at': validation_date
                })
        
        if case.assigned_to:
            assignment_exists = history.filter(
                action__in=['assignment', 'agent_assigned']
            ).exists()
            if not assignment_exists:
                assignment_date = case.updated_at if hasattr(case, 'updated_at') and case.updated_at else case.created_at
                agent_name = case.assigned_to.get_full_name() if hasattr(case.assigned_to, 'get_full_name') else (case.assigned_to.username if hasattr(case.assigned_to, 'username') else str(case.assigned_to))
                system_events.append({
                    'event_type': 'Assignment',
                    'event_description': f"Case assigned to agent {agent_name}",
                    'event_date': assignment_date.strftime('%d/%m/%Y'),
                    'event_time': assignment_date.strftime('%H:%M:%S'),
                    'performed_by': 'System',
                    'created_at': assignment_date
                })
        
        all_history = list(history_serializer.data)
        existing_event_types = {h.get('event_type') for h in all_history}
        
        for event in system_events:
            if event['event_type'] not in existing_event_types:
                all_history.append(event)
        
        def sort_key(event):
            try:
                date_str = event.get('event_date', '')
                time_str = event.get('event_time', '00:00:00')
                if date_str and time_str:
                    dt_str = f"{date_str} {time_str}"
                    return datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
            except:
                pass
            if 'created_at' in event:
                return event['created_at']
            return datetime.min
        
        all_history.sort(key=sort_key)
        
        for event in all_history:
            if 'created_at' in event:
                del event['created_at']
        
        summary_serializer = CaseTimelineSummarySerializer(
            case, 
            context={'request': request}
        )
        
        case_logs = CaseLog.objects.filter(
            renewal_case=case, 
            is_deleted=False
        ).select_related('created_by', 'updated_by').order_by('-created_at')
        case_logs_serializer = CaseLogSerializer(
            case_logs, 
            many=True, 
            context={'request': request}
        )
        
        return Response({
            'journey_summary': summary_serializer.data,
            'case_history': all_history,
            'case_logs': case_logs_serializer.data,
        })
        
    except PermissionDenied:
        raise
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error retrieving timeline: {str(e)}',
            'data': None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ClosedCasesCommentListView(generics.ListCreateAPIView):
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['comment_type', 'is_internal', 'is_important', 'created_by']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            from apps.case_logs.serializers import CaseCommentSerializer
            return CaseCommentSerializer
        from apps.case_logs.serializers import CaseCommentCreateSerializer
        return CaseCommentCreateSerializer
    
    def get_queryset(self):
        """Get comments for the specified case (only if case is renewed) using CaseLog."""
        from apps.case_logs.models import CaseLog
        
        case_number = self.kwargs['case_number']
        
        case = RenewalCase.objects.filter(
            case_number__iexact=case_number,
            status='renewed', 
            is_deleted=False
        ).first()
        
        if not case:
            return CaseLog.objects.none()
        
        if not (self.request.user.is_staff or 
                case.assigned_to == self.request.user or 
                case.created_by == self.request.user):
            return CaseLog.objects.none()
        
        return CaseLog.objects.filter(renewal_case=case, is_deleted=False).exclude(comment='').exclude(comment__isnull=True)
    
    def create(self, request, *args, **kwargs):
        """Create a new comment for the specified case (only if case is renewed) using CaseLog."""
        from apps.case_logs.serializers import CaseCommentCreateSerializer, CaseCommentSerializer
        
        case_number = self.kwargs['case_number']
        
        case = RenewalCase.objects.filter(
            case_number__iexact=case_number,
            status='renewed', 
            is_deleted=False
        ).first()
        
        if not case:
            return Response({
                'success': False,
                'message': 'Renewal case not found or case is not renewed',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not (request.user.is_staff or 
                case.assigned_to == request.user or 
                case.created_by == request.user):
            return Response({
                'success': False,
                'message': "You don't have permission to add comments to this case.",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = CaseCommentCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        comment = serializer.save(renewal_case=case)
        
        response_serializer = CaseCommentSerializer(comment, context={'request': request})
        return Response({
            'success': True,
            'message': 'Comment created successfully',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)
class ClosedCasesCommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        from apps.case_logs.serializers import CaseCommentSerializer
        return CaseCommentSerializer
    
    def get_queryset(self):
        """Get comments for the specified case (only if case is renewed) using CaseLog."""
        from apps.case_logs.models import CaseLog
        
        case_number = self.kwargs['case_number']
        
        case = RenewalCase.objects.filter(
            case_number__iexact=case_number,
            status='renewed', 
            is_deleted=False
        ).first()
        
        if not case:
            return CaseLog.objects.none()
        
        if not (self.request.user.is_staff or 
                case.assigned_to == self.request.user or 
                case.created_by == self.request.user):
            return CaseLog.objects.none()
        
        return CaseLog.objects.filter(renewal_case=case, is_deleted=False).exclude(comment='').exclude(comment__isnull=True)
    
    def perform_update(self, serializer):
        """Update comment and create history entry."""
        from apps.case_history.models import CaseHistory
        
        comment = serializer.save()
        
        CaseHistory.objects.create(
            case=comment.renewal_case,
            action='comment_updated',
            description=f"Comment updated: {comment.comment[:100]}{'...' if len(comment.comment) > 100 else ''}",
            created_by=self.request.user
        )
    
    def perform_destroy(self, instance):
        """Delete comment and create history entry."""
        from apps.case_history.models import CaseHistory
        
        CaseHistory.objects.create(
            case=instance.renewal_case,
            action='comment_deleted',
            description=f"Comment deleted: {instance.comment[:100]}{'...' if len(instance.comment) > 100 else ''}",
            created_by=self.request.user
        )
        
        instance.delete(user=self.request.user)

class ClosedCasesUpdateStatusView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'case_number'
    
    def get_serializer_class(self):
        from apps.case_history.serializers import UpdateCaseStatusSerializer
        return UpdateCaseStatusSerializer
    
    def get_queryset(self):
        """Filter cases - only renewed cases"""
        queryset = RenewalCase.objects.filter(
            status='renewed',
            is_deleted=False
        )
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(assigned_to=self.request.user)
        
        return queryset
    
    def update(self, request, *args, **kwargs):
        """Handle PUT/PATCH request to update case status and related fields."""
        partial = kwargs.pop('partial', False)
        
        case_number = self.kwargs['case_number']
        
        case = RenewalCase.objects.filter(
            case_number__iexact=case_number,
            status='renewed',
            is_deleted=False
        ).first()
        
        if not case:
            return Response({
                'success': False,
                'message': 'Renewal case not found or case is not renewed',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not (request.user.is_staff or 
                case.assigned_to == request.user or 
                case.created_by == request.user):
            return Response({
                'success': False,
                'message': "You don't have permission to update this case.",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(case, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        case.refresh_from_db()
        
        return Response({
            'success': True,
            'message': 'Case status updated successfully',
            'data': {
                'case_number': case.case_number,
                'status': case.status,
                'follow_up_date': case.follow_up_date.isoformat() if case.follow_up_date else None,
                'follow_up_time': case.follow_up_time.isoformat() if case.follow_up_time else None,
                'remarks': case.remarks,
            }
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_closed_case_outstanding_summary_api(request, case_id):
    try:
        if case_id.isdigit():
            renewal_case = RenewalCase.objects.filter(
                id=int(case_id),
                status__in=['completed', 'renewed'],
                policy__status='active'
            ).first()
            actual_case_id = int(case_id)
        else:
            renewal_case = RenewalCase.objects.filter(
                case_number=case_id,
                status__in=['completed', 'renewed'],
                policy__status='active'
            ).first()
            if renewal_case:
                actual_case_id = renewal_case.id
            else:
                actual_case_id = None
        
        if not renewal_case:
            return Response({
                'success': False,
                'error': 'Case Not Renewed'
            }, status=status.HTTP_404_NOT_FOUND)
        
        outstanding_data = OutstandingAmountsService.get_outstanding_summary(actual_case_id)
        
        if outstanding_data is None:
            return Response({
                'success': False,
                'error': 'Failed to calculate outstanding amounts'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        serializer = OutstandingAmountsSummarySerializer(outstanding_data)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to fetch outstanding amounts',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_closed_case_customer_insights_api(request, case_number):
    try:
        force_recalculate = request.query_params.get('force_recalculate', 'false').lower() == 'true'
        
        sections = request.query_params.get('sections', '').split(',')
        sections = [s.strip() for s in sections if s.strip()]
        
        renewal_case = RenewalCase.objects.filter(
            case_number=case_number,
            status__in=['completed', 'renewed'],
            policy__status='active'
        ).select_related('customer').first()
        
        if not renewal_case:
            return Response({
                'success': False,
                'message': 'Case Not Renewed',
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        
        customer = renewal_case.customer
        
        service = CustomerInsightsService()
        insights_data = service.get_customer_insights(customer.id, force_recalculate)
        
        if 'error' in insights_data:
            return Response({
                'success': False,
                'error': insights_data['error'],
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)
        
        if sections:
            filtered_data = {
                'customer_info': insights_data['customer_info'],
                'calculated_at': insights_data['calculated_at'],
                'is_cached': insights_data['is_cached']
            }
            
            for section in sections:
                if section in insights_data:
                    filtered_data[section] = insights_data[section]
            
            insights_data = filtered_data
        
        serializer = CustomerInsightsResponseSerializer(insights_data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to fetch customer insights',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_closed_case_communication_history_api(request, case_number):
    try:
        renewal_case = RenewalCase.objects.filter(
            case_number=case_number,
            status__in=['completed', 'renewed'],
            policy__status='active'
        ).select_related('customer').first()
        
        if not renewal_case:
            return Response({
                'success': False,
                'message': 'Case Not Renewed'
            }, status=status.HTTP_404_NOT_FOUND)
        
        customer = renewal_case.customer
        
        service = CustomerInsightsService()
        history_data = service.get_communication_history(customer)
        
        serializer = CommunicationHistoryResponseSerializer(history_data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to fetch communication history',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_closed_case_claims_history_api(request, case_number):
    try:
        renewal_case = RenewalCase.objects.filter(
            case_number=case_number,
            status__in=['completed', 'renewed'],
            policy__status='active'
        ).select_related('customer').first()
        
        if not renewal_case:
            return Response({
                'success': False,
                'message': 'Case Not Renewed'
            }, status=status.HTTP_404_NOT_FOUND)
        
        customer = renewal_case.customer
        
        service = CustomerInsightsService()
        history_data = service.get_claims_history(customer)
        
        serializer = ClaimsHistoryResponseSerializer(history_data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to fetch claims history',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
