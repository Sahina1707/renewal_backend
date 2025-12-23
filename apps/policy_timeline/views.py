"""
Policy Timeline views for the Intelipro Insurance Policy Renewal System.
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone 
from datetime import timedelta

# Import models/serializers from current app (assuming the Payment Schedule classes are here)
from .models import PolicyTimeline, CustomerTimelineSummary, UpcomingPayment, CustomerPaymentSchedule
from .serializers import (
    PolicyTimelineSerializer,
    PolicyTimelineDetailSerializer,
    PolicyTimelineCreateSerializer,
    CustomerPaymentScheduleSerializer, 
    UpcomingPaymentSerializer
)

# You must ensure these external imports are correct for your project structure
from apps.policies.models import Policy
from apps.customers.models import Customer
from apps.renewal_timeline.models import CommonRenewalTimelineSettings


class PolicyTimelineListCreateView(generics.ListCreateAPIView):
    """
    List all policy timeline events or create a new timeline event
    """
    queryset = PolicyTimeline.objects.select_related('policy', 'customer', 'agent')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PolicyTimelineCreateSerializer
        return PolicyTimelineSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        policy_id = self.request.query_params.get('policy_id')
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        milestones_only = self.request.query_params.get('milestones_only')
        if milestones_only and milestones_only.lower() == 'true':
            queryset = queryset.filter(is_milestone=True)
        
        return queryset.filter(is_deleted=False)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PolicyTimelineDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a policy timeline event
    """
    queryset = PolicyTimeline.objects.select_related('policy', 'customer', 'agent')
    serializer_class = PolicyTimelineDetailSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        instance.delete(user=self.request.user)


@api_view(['GET'])
def policy_timeline_by_policy(request, policy_id):
    """
    Get timeline events for a specific policy
    """
    try:
        policy = get_object_or_404(Policy, id=policy_id)
        timeline_events = PolicyTimeline.objects.filter(
            policy=policy,
            is_deleted=False
        ).select_related('policy', 'customer', 'agent').order_by('-event_date')
        
        serializer = PolicyTimelineSerializer(timeline_events, many=True)
        
        return Response({
            'success': True,
            'policy_number': policy.policy_number,
            'customer_name': policy.customer.full_name,
            'timeline_events': serializer.data,
            'total_events': timeline_events.count()
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def customer_policy_timeline(request, customer_id):
    """
    Get all timeline events for a specific customer across all their policies
    """
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        timeline_events = PolicyTimeline.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related('policy', 'customer', 'agent').order_by('-event_date')
        
        serializer = PolicyTimelineSerializer(timeline_events, many=True)
        
        return Response({
            'success': True,
            'customer_name': customer.full_name,
            'customer_code': customer.customer_code,
            'timeline_events': serializer.data,
            'total_events': timeline_events.count()
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def timeline_event_types(request):
    """
    Get available event types for timeline
    """
    event_types = [
        {'value': choice[0], 'label': choice[1]} 
        for choice in PolicyTimeline.EVENT_TYPE_CHOICES
    ]
    
    event_statuses = [
        {'value': choice[0], 'label': choice[1]} 
        for choice in PolicyTimeline.EVENT_STATUS_CHOICES
    ]
    
    return Response({
        'success': True,
        'event_types': event_types,
        'event_statuses': event_statuses
    })


@api_view(['POST'])
def create_timeline_event(request):
    """
    Create a new timeline event
    """
    try:
        serializer = PolicyTimelineCreateSerializer(data=request.data)
        if serializer.is_valid():
            timeline_event = serializer.save(created_by=request.user)
            
            response_serializer = PolicyTimelineDetailSerializer(timeline_event)
            
            return Response({
                'success': True,
                'message': 'Timeline event created successfully',
                'timeline_event': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def policy_timeline_dashboard(request, customer_id):
    """
    Get comprehensive policy timeline dashboard data for a customer
    """
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        
        timeline_events = PolicyTimeline.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related('policy', 'customer', 'agent').order_by('-event_date')
        
        try:
            summary = customer.timeline_summary
        except:
            summary = CustomerTimelineSummary.objects.create(
                customer=customer,
                total_events=timeline_events.count(),
                active_policies=customer.policies.filter(status='active').count(),
                total_premium=sum([float(p.premium_amount or 0) for p in customer.policies.filter(status='active')])
            )
        
        return Response({
            'success': True,
            'customer': {
                'id': customer.id,
                'name': customer.full_name,
                'code': customer.customer_code,
            },
            'total_events': timeline_events.count()
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def policy_timeline_complete_view(request, customer_id):
    """
    Get complete policy timeline view with all related customer data
    """
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        
        latest_timeline = PolicyTimeline.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related('policy', 'customer', 'agent').order_by('-event_date').first()
        
        if not latest_timeline:
            return Response({
                'success': False,
                'error': 'No timeline events found for this customer'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def search_timeline_events(request):
    """
    Search timeline events with filters
    """
    try:
        queryset = PolicyTimeline.objects.select_related('policy', 'customer', 'agent').filter(is_deleted=False)
        
        search_query = request.query_params.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(event_title__icontains=search_query) |
                Q(event_description__icontains=search_query) |
                Q(policy__policy_number__icontains=search_query) |
                Q(customer__full_name__icontains=search_query)
            )
        
        event_type = request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(event_date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(event_date__date__lte=end_date)
        
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        policy_id = request.query_params.get('policy_id')
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        
        queryset = queryset.order_by('-event_date')
        
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = queryset.count()
        events = queryset[start:end]
        
        serializer = PolicyTimelineSerializer(events, many=True)
        
        return Response({
            'success': True,
            'results': serializer.data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def timeline_statistics(request):
    """
    Get timeline statistics and analytics
    """
    try:
        from django.db.models import Count, Q
        
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        total_events = PolicyTimeline.objects.filter(is_deleted=False).count()
        recent_events = PolicyTimeline.objects.filter(
            is_deleted=False,
            event_date__gte=start_date
        ).count()
        
        events_by_type = PolicyTimeline.objects.filter(
            is_deleted=False,
            event_date__gte=start_date
        ).values('event_type').annotate(count=Count('id')).order_by('-count')
        
        events_by_status = PolicyTimeline.objects.filter(
            is_deleted=False,
            event_date__gte=start_date
        ).values('event_status').annotate(count=Count('id')).order_by('-count')
        
        milestone_events = PolicyTimeline.objects.filter(
            is_deleted=False,
            is_milestone=True,
            event_date__gte=start_date
        ).count()
        
        follow_up_events = PolicyTimeline.objects.filter(
            is_deleted=False,
            follow_up_required=True,
            follow_up_date__gte=timezone.now().date()
        ).count()
        
        return Response({
            'success': True,
            'statistics': {
                'total_events': total_events,
                'recent_events': recent_events,
                'milestone_events': milestone_events,
                'follow_up_events': follow_up_events,
                'events_by_type': list(events_by_type),
                'events_by_status': list(events_by_status),
                'date_range': {
                    'start_date': start_date.date(),
                    'end_date': end_date.date(),
                    'days': days
                }
            }
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def create_timeline_event_bulk(request):
    """
    Create multiple timeline events in bulk
    """
    try:
        events_data = request.data.get('events', [])
        if not events_data:
            return Response({
                'success': False,
                'error': 'No events data provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        created_events = []
        errors = []
        
        for event_data in events_data:
            serializer = PolicyTimelineCreateSerializer(data=event_data)
            if serializer.is_valid():
                event = serializer.save(created_by=request.user)
                created_events.append(event)
            else:
                errors.append({
                    'data': event_data,
                    'errors': serializer.errors
                })
        
        response_data = {
            'success': True,
            'created_count': len(created_events),
            'error_count': len(errors),
            'created_events': PolicyTimelineSerializer(created_events, many=True).data
        }
        
        if errors:
            response_data['errors'] = errors
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def policy_timeline_complete_api(request, customer_id):
    """
    COMPLETE POLICY TIMELINE API - Single endpoint for all frontend data
    
    This API provides everything needed for the policy timeline frontend:
    - Customer information, Financial profile, Assets, Medical history
    - Communication & Policy preferences
    - Payment schedules (summary and upcoming list)
    - Timeline events with filtering
    """
    try:
        # FIX 1: Use select_related to load the payment schedule summary immediately
        customer = get_object_or_404(
            Customer.objects.select_related('payment_schedule'), 
            id=customer_id
        )
        
        # 1. Get timeline events with filtering
        timeline_queryset = PolicyTimeline.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related('policy', 'customer', 'agent').order_by('-event_date')
        
        # Apply filters (search, event_type, date range)
        search_query = request.query_params.get('search', '')
        if search_query:
            timeline_queryset = timeline_queryset.filter(
                Q(event_title__icontains=search_query) |
                Q(event_description__icontains=search_query) |
                Q(policy__policy_number__icontains=search_query)
            )
        event_type = request.query_params.get('event_type')
        if event_type:
            timeline_queryset = timeline_queryset.filter(event_type=event_type)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            timeline_queryset = timeline_queryset.filter(event_date__date__gte=start_date)
        if end_date:
            timeline_queryset = timeline_queryset.filter(event_date__date__lte=end_date)
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        total_events_count = timeline_queryset.count()
        timeline_events = timeline_queryset[start:end]
        
        # 2. Get or create customer timeline summary
        try:
            summary = customer.timeline_summary
        except:
            summary = CustomerTimelineSummary.objects.create(
                customer=customer,
                total_events=total_events_count,
                active_policies=customer.policies.filter(status='active').count(),
                total_premium=sum([float(p.premium_amount or 0) for p in customer.policies.filter(status='active')])
            )
        
        # Serialize data
        timeline_serializer = PolicyTimelineSerializer(timeline_events, many=True)
        
        # 3. Get customer's active policies and calculate financial stats
        active_policies = customer.policies.filter(status='active')
        policies_data = []
        total_premium = 0
        total_coverage = 0
        for policy in active_policies:
            premium = float(policy.premium_amount or 0)
            coverage = float(policy.sum_assured or 0)
            total_premium += premium
            total_coverage += coverage
            
            policies_data.append({
                'id': policy.id,
                'policy_number': policy.policy_number,
                'policy_type': policy.policy_type.name if policy.policy_type else None,
                'premium_amount': premium,
                'start_date': policy.start_date,
                'end_date': policy.end_date,
                'status': policy.status,
                'coverage_amount': coverage, 
            })
        
        payment_schedules = None
        upcoming_payments_data = []
        schedule_summary = None
        
        try:
            # Use get_or_create to ensure schedule exists
            schedule_summary, created = CustomerPaymentSchedule.objects.get_or_create(
                customer=customer,
                defaults={
                    'average_payment_timing_days': 5,
                    'preferred_payment_method': 'credit_card',
                    'total_payments_last_12_months': 12
                }
            )
            
            if schedule_summary:
                payment_schedules = CustomerPaymentScheduleSerializer(schedule_summary).data
                
                # Fetch Upcoming Payments list
                upcoming_payments = UpcomingPayment.objects.filter(
                    customer=customer,
                    due_date__gte=timezone.now().date()
                ).select_related('policy').order_by('due_date')
                upcoming_payments_data = UpcomingPaymentSerializer(upcoming_payments, many=True).data
        
            
        except CustomerPaymentSchedule.DoesNotExist:
            pass
        except Exception as e:
            pass # Catch other serialization errors

        
        # 5. Get Financial Profile
        financial_profile = None
        try:
            if customer.financial_profile:
                financial_profile = {
                    'annual_income': float(customer.financial_profile.annual_income or 0),
                    'income_captured_date': customer.financial_profile.income_captured_date,
                    'income_source': customer.financial_profile.income_source,
                    'policy_capacity_utilization': customer.financial_profile.policy_capacity_utilization,
                    'recommended_policies_count': customer.financial_profile.recommended_policies_count,
                    'risk_profile': customer.financial_profile.risk_profile,
                    'tolerance_score': float(customer.financial_profile.tolerance_score or 0),
                    'income_range': customer.financial_profile.income_range,
                    'capacity_status': customer.financial_profile.capacity_status,
                }
        except:
            pass
        
        # 6. Get Family Medical History
        medical_history = []
        try:
            for history in customer.family_medical_history.filter(is_active=True):
                medical_history.append({
                    'condition_name': history.condition_name,
                    'family_relation': history.get_family_relation_display(),
                    'condition_status': history.get_condition_status_display(),
                    'age_diagnosed': history.age_diagnosed,
                    'severity_level': history.get_severity_level_display(),
                    'risk_score': history.risk_score,
                    'is_high_risk': history.is_high_risk,
                })
        except:
            pass
        
        # 7. Get Assets and Vehicles
        assets_data = []
        vehicles_data = []
        try:
            for asset in customer.assets.all():
                assets_data.append({
                    'residence_type': asset.get_residence_type_display(),
                    'residence_status': asset.get_residence_status_display(),
                    'residence_location': asset.residence_location,
                    'residence_rating': asset.get_residence_rating_display(),
                    'asset_score': asset.asset_score,
                })
                for vehicle in asset.vehicles.all():
                    vehicles_data.append({
                        'vehicle_name': vehicle.vehicle_name,
                        'model_year': vehicle.model_year,
                        'vehicle_type': vehicle.get_vehicle_type_display(),
                        'value': float(vehicle.value),
                        'condition': vehicle.get_condition_display(),
                        'vehicle_age': vehicle.vehicle_age,
                        'vehicle_score': vehicle.vehicle_score,
                    })
        except:
            pass
        
        # 9. Get Policy Preferences (INCLUDING AVOIDED TYPES)
        policy_preferences = []
        try:
            for pref in customer.policy_preferences.all():
                policy_preferences.append({
                    'preferred_tenure': pref.preferred_tenure,
                    'coverage_type': pref.get_coverage_type_display(),
                    'preferred_insurer': pref.preferred_insurer,
                    'payment_mode': pref.get_payment_mode_display(),
                    'auto_renewal': pref.auto_renewal,
                    'budget_range_min': float(pref.budget_range_min or 0),
                    'budget_range_max': float(pref.budget_range_max or 0),
                    'avoided_policy_types': pref.avoided_policy_types if hasattr(pref, 'avoided_policy_types') else None, 
                })
        except:
            pass
        
        # 10. Get Other Insurance Policies
        other_policies = []
        try:
            for policy in customer.other_insurance_policies.filter(policy_status='active'):
                other_policies.append({
                    'policy_number': policy.policy_number,
                    'insurance_company': policy.insurance_company,
                    'policy_type': policy.policy_type.name if policy.policy_type else None,
                    'premium_amount': float(policy.premium_amount),
                    'sum_assured': float(policy.sum_assured),
                    'payment_mode': policy.get_payment_mode_display(),
                    'channel': policy.get_channel_display(),
                    'satisfaction_rating': policy.satisfaction_rating,
                    'claim_experience': policy.claim_experience,
                    'switching_potential': policy.switching_potential,
                })
        except:
            pass
        
        # 11. Get AI Insights and Recommendations (Completely Omitted as requested)
        
        
        # 12. Get Event Type Counts
        event_type_counts = {}
        for event_type_choice in PolicyTimeline.EVENT_TYPE_CHOICES:
            count = PolicyTimeline.objects.filter(
                customer=customer,
                event_type=event_type_choice[0],
                is_deleted=False
            ).count()
            event_type_counts[event_type_choice[0]] = {
                'label': event_type_choice[1],
                'count': count
            }
                
        # A. Communication Preferences
        comm_prefs_data = []
        try:
            for pref in customer.detailed_communication_preferences.all():
                comm_prefs_data.append({
                    'channel': pref.get_preferred_channel_display(),
                    'status': 'Preferred' if getattr(pref, 'is_preferred', False) else 'Accepted',
                    'is_enabled': True
                })
        except:
            pass

        # B. Renewal Timeline
        renewal_data = None
        try:
            # Fetch global settings for reminders to match case_details view
            common_settings = CommonRenewalTimelineSettings.objects.filter(is_active=True).first()
            reminder_schedule = []
            
            if common_settings:
                if common_settings.reminder_schedule:
                    reminder_schedule = common_settings.reminder_schedule
                elif hasattr(common_settings, 'reminder_days') and common_settings.reminder_days:
                    for days in common_settings.reminder_days:
                        if days == 30:
                            reminder_schedule.append("30 days before due date (Email)")
                        elif days == 14:
                            reminder_schedule.append("14 days before due date (Email)")
                        elif days == 7:
                            reminder_schedule.append("7 days before due date (Phone)")
                        else:
                            reminder_schedule.append(f"{days} days before due date (Email)")
            
            if not reminder_schedule:
                reminder_schedule = ["30 days before due date (Email)", "14 days before due date (Email)", "7 days before due date (Phone)"]

            if schedule_summary:
                avg_days = schedule_summary.average_payment_timing_days
                timing_str = f"Pays {abs(avg_days)} days {'early' if avg_days >= 0 else 'late'}"
                
                renewal_data = {
                    'typical_pattern': timing_str, 
                    'avg_timing_days': avg_days,
                    'reminder_schedule': reminder_schedule
                }
        except:
            renewal_data = None

        # C. Payment Methods
        payment_method_data = None
        try:
            if schedule_summary:
                payment_method_data = {
                    'primary_method': schedule_summary.get_preferred_payment_method_display(),
                    'auto_debit_active': schedule_summary.preferred_payment_method == 'auto_debit',
                    'details': "Details on file" 
                }
        except:
            payment_method_data = None

        # D. Language Preferences
        language_data = {
            'preferred_language': getattr(customer, 'preferred_language', 'English'),
            'document_language': getattr(customer, 'document_language', 'English'),
            'primary_communication_language': getattr(customer, 'communication_language', 'English')
        }

        customer_preferences_consolidated = {
            'communication': comm_prefs_data,
            'renewal_timeline': renewal_data,
            'payment_methods': payment_method_data,
            'languages': language_data
        }

        return Response({
            'success': True,
            'data': {
                'customer': {
                    'id': customer.id,
                    'name': customer.full_name,
                    'code': customer.customer_code,
                    'email': customer.email,
                    'phone': customer.phone,
                    'date_of_birth': customer.date_of_birth,
                    'gender': customer.gender,
                    'address': f"{customer.address_line1}, {customer.city}, {customer.state}" if customer.address_line1 else None,
                },
                'summary': {
                    'total_events': total_events_count,
                    'active_policies': len(policies_data),
                    'total_premium': total_premium,
                    'total_coverage': total_coverage,
                    'last_activity_date': timeline_events[0].event_date if timeline_events else None,
                },
                'financial_profile': financial_profile,
                'family_medical_history': medical_history,
                'assets': assets_data,
                'vehicles': vehicles_data,
                'policy_preferences': policy_preferences,
                'other_insurance_policies': other_policies,
                'customer_preferences': customer_preferences_consolidated,
                
                
                'payment_schedules': {
                    'summary': payment_schedules,
                    'upcoming_payments': upcoming_payments_data,
                },
                'active_policies': policies_data,
                'timeline_events': {
                    'results': timeline_serializer.data,
                    'total_count': total_events_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_events_count + page_size - 1) // page_size,
                    'event_type_counts': event_type_counts,
                },
                'filters': {
                    'search_query': search_query,
                    'event_type': event_type,
                    'start_date': start_date,
                    'end_date': end_date,
                }
            }
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
# ... (rest of the file containing check_data_completeness and policy_data_check_generic follows) ... 
def check_data_completeness(data, policy_type_slug):
    """Internal helper function to check completeness based on dynamic policy type."""
    
    slug = policy_type_slug.upper()
    
    # Financial data exists and income is > 0
    financial_ok = data['financial_profile'] is not None and data['financial_profile'].get('annual_income', 0) > 0
    # Communication preferences are set
    communication_ok = len(data['communication_preferences']) > 0
    # Policy preferences exist and budget is set
    preferences_ok = len(data['policy_preferences']) > 0 and data['policy_preferences'][0].get('budget_range_max', 0) > 0
    
    # Policy-Specific Checks
    policy_specific_ok = False
    policy_focus = slug

    if 'VEHICLE' in slug:
        # Vehicle: Check for vehicle assets
        policy_specific_ok = len(data['vehicles']) > 0
        policy_focus = 'VEHICLE'
    
    elif 'LIFE' in slug or 'HEALTH' in slug:
        # Life/Health: Check for medical history (critical for underwriting)
        policy_specific_ok = len(data['family_medical_history']) > 0
        policy_focus = 'LIFE/HEALTH'
        
    elif 'HOME' in slug or 'PROPERTY' in slug:
        # Property/Home: Check for residence/asset details (at least one asset)
        policy_specific_ok = len(data['assets']) > 0
        policy_focus = 'PROPERTY/HOME'
        
    else:
        # General/Other: Assume general data is sufficient
        policy_specific_ok = True 
        policy_focus = slug
    
    return {
        "policy_focus": policy_focus,
        "financial_profile": financial_ok,
        "communication_preferences": communication_ok,
        "policy_preferences": preferences_ok,
        "policy_specific_data": policy_specific_ok,
        "overall_complete": all([financial_ok, communication_ok, preferences_ok, policy_specific_ok])
    }


@api_view(['GET'])
def policy_data_check_generic(request, policy_type_slug, customer_id):
    """
    Generic API to check data completeness for any policy type (Vehicle, Life, Home, etc.).
    
    URL: /data-check/<policy_type_slug>/<customer_id>/
    """
    try:
        # 1. Fetch all comprehensive data using the existing endpoint
        raw_django_request = request._request
        complete_response = policy_timeline_complete_api(request, customer_id)
        
        if complete_response.status_code != 200:
            return complete_response 
        complete_data = complete_response.data['data']
        
        # 2. Determine completeness status based on the slug
        completeness_status = check_data_completeness(complete_data, policy_type_slug)
        
        # 3. Filter active policies for the specific type
        policy_type_filter = completeness_status['policy_focus'].split('/')[0].upper()
        
        target_policies = [
            p for p in complete_data['active_policies'] 
            if p.get('policy_type') and policy_type_filter in p['policy_type'].upper()
        ]
        
        return Response({
            'success': True,
            'customer_id': customer_id,
            'policy_type_requested': completeness_status['policy_focus'],
            'active_policies': target_policies,
            'data_completeness': completeness_status
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)