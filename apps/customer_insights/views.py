"""
API views for Customer Insights endpoints.
Simplified design with single main endpoint and consolidated functionality.
"""

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from apps.claims.models import Claim
from apps.customers.models import Customer
from .models import CustomerInsight
from .serializers import (
    CustomerInsightsResponseSerializer, CustomerInsightSerializer,
    CustomerInsightsSummarySerializer, InsightsDashboardSerializer,
    CustomerInsightsFilterSerializer, CustomerInsightsBulkUpdateSerializer,
    CustomerInsightsRecalculateSerializer,
    CommunicationHistoryResponseSerializer, ClaimsHistoryResponseSerializer 
)
from .services import CustomerInsightsService


class CustomerInsightsViewSet(viewsets.ModelViewSet):
    """ViewSet for customer insights operations - simplified"""
    
    queryset = CustomerInsight.objects.all()
    serializer_class = CustomerInsightSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        return queryset.order_by('-calculated_at')
    
    @action(detail=False, methods=['get'], url_path='customer/(?P<case_number>[^/.]+)')
    def get_customer_insights(self, request, case_number=None):
        """Get comprehensive insights for a specific customer - MAIN ENDPOINT"""
        try:
            force_recalculate = request.query_params.get('force_recalculate', 'false').lower() == 'true'
            
            sections = request.query_params.get('sections', '').split(',')
            sections = [s.strip() for s in sections if s.strip()]
            
            try:
                from apps.renewals.models import RenewalCase
                renewal_case = RenewalCase.objects.select_related('customer').get(case_number=case_number)
                customer = renewal_case.customer
            except RenewalCase.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Case with number {case_number} not found',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)
            
            service = CustomerInsightsService()
            insights_data = service.get_customer_insights(customer.id, force_recalculate)
            
            if 'error' in insights_data:
                return Response(
                    {'error': insights_data['error']}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
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
            
        except ValueError:
            return Response(
                {'error': 'Invalid customer ID'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to get customer insights: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='customer/(?P<case_number>[^/.]+)/recalculate')
    def recalculate_insights(self, request, case_number=None):
        """Recalculate insights for a specific customer"""
        try:
            serializer = CustomerInsightsRecalculateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            force_recalculate = serializer.validated_data.get('force_recalculate', False)
            sections = serializer.validated_data.get('sections', [])
            
            try:
                from apps.renewals.models import RenewalCase
                renewal_case = RenewalCase.objects.select_related('customer').get(case_number=case_number)
                customer = renewal_case.customer
            except RenewalCase.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Case with number {case_number} not found',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)
            
            service = CustomerInsightsService()
            insights_data = service.get_customer_insights(customer.id, force_recalculate=True)
            
            if 'error' in insights_data:
                return Response(
                    {'error': insights_data['error']}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response({
                'message': 'Insights recalculated successfully',
                'data': insights_data
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response(
                {'error': 'Invalid customer ID'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to recalculate insights: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
    @action(detail=False, methods=['post'], url_path='bulk-update')
    def bulk_update_insights(self, request):
        """Bulk update insights for multiple customers"""
        serializer = CustomerInsightsBulkUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            customer_ids = serializer.validated_data['customer_ids']
            force_recalculate = serializer.validated_data['force_recalculate']
            
            service = CustomerInsightsService()
            updated_count = 0
            
            for customer_id in customer_ids:
                try:
                    customer = Customer.objects.get(id=customer_id, is_deleted=False)
                    service.get_customer_insights(customer_id)
                    updated_count += 1
                except Customer.DoesNotExist:
                    continue
            
            return Response({
                'message': f'Successfully updated insights for {updated_count} customers',
                'updated_count': updated_count,
                'total_requested': len(customer_ids)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to bulk update insights: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='dashboard')
    def get_insights_dashboard(self, request):
        """Get insights dashboard data"""
        try:
            total_customers = Customer.objects.filter(is_deleted=False).count()
            
            high_value_customers = Customer.objects.filter(
                is_deleted=False,
                profile='HNI'
            ).count()
            
            # Customers with claims (mock data)
            customers_with_claims = Claim.objects.values('customer_id').distinct().count()            
            # Average satisfaction rating (from JSON fields)
            avg_satisfaction = 0.0
            total_premiums = 0.0
            payment_reliability_avg = 0.0
            
            insights_records = CustomerInsight.objects.all()
            if insights_records.exists():
                satisfaction_ratings = []
                premium_totals = []
                payment_rates = []
                
                for record in insights_records:
                    comm_insights = record.communication_insights
                    pay_insights = record.payment_insights
                    
                    if comm_insights.get('satisfaction_rating'):
                        satisfaction_ratings.append(comm_insights['satisfaction_rating'])
                    
                    if pay_insights.get('total_premiums_paid'):
                        premium_totals.append(pay_insights['total_premiums_paid'])
                    
                    if pay_insights.get('on_time_payment_rate'):
                        payment_rates.append(pay_insights['on_time_payment_rate'])
                
                avg_satisfaction = sum(satisfaction_ratings) / len(satisfaction_ratings) if satisfaction_ratings else 0.0
                total_premiums = sum(premium_totals) if premium_totals else 0.0
                payment_reliability_avg = sum(payment_rates) / len(payment_rates) if payment_rates else 0.0
            
            recent_insights = []
            recent_customers = Customer.objects.filter(
                is_deleted=False,
                customer_insights__isnull=False
            ).distinct().order_by('-customer_insights__calculated_at')[:10]
            
            for customer in recent_customers:
                try:
                    insight_record = CustomerInsight.objects.get(customer=customer)
                    payment_insights = insight_record.payment_insights
                    communication_insights = insight_record.communication_insights
                    claims_insights = insight_record.claims_insights
                    profile_insights = insight_record.profile_insights
                    
                    recent_insights.append({
                        'customer_id': customer.id,
                        'customer_name': customer.full_name,
                        'customer_code': customer.customer_code,
                        'total_premiums_paid': payment_insights.get('total_premiums_paid', 0),
                        'on_time_payment_rate': payment_insights.get('on_time_payment_rate', 0),
                        'total_communications': communication_insights.get('total_communications', 0),
                        'satisfaction_rating': communication_insights.get('satisfaction_rating', 0),
                        'total_claims': claims_insights.get('total_claims', 0),
                        'approval_rate': claims_insights.get('approval_rate', 0),
                        'risk_level': claims_insights.get('risk_level', 'low'),
                        'customer_segment': profile_insights.get('customer_segment', 'Standard'),
                        'last_updated': insight_record.updated_at,
                    })
                except CustomerInsight.DoesNotExist:
                    continue
            
            dashboard_data = {
                'total_customers': total_customers,
                'high_value_customers': high_value_customers,
                'customers_with_claims': customers_with_claims,
                'avg_satisfaction_rating': round(avg_satisfaction, 1),
                'total_premiums_collected': total_premiums,
                'payment_reliability_avg': round(payment_reliability_avg, 1),
                'recent_insights': recent_insights,
            }
            
            serializer = InsightsDashboardSerializer(dashboard_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to get dashboard data: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='summary')
    def get_insights_summary(self, request):
        """Get filtered insights summary"""
        filter_serializer = CustomerInsightsFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(filter_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            filters = filter_serializer.validated_data
            limit = filters.get('limit', 50)
            offset = filters.get('offset', 0)
            
            # Build query filters
            queryset = Customer.objects.filter(is_deleted=False)
            
            if filters.get('customer_segment'):
                queryset = queryset.filter(
                    customer_insights__profile_insights__customer_segment=filters['customer_segment']
                )
            
            if filters.get('risk_level'):
                queryset = queryset.filter(
                    customer_insights__claims_insights__risk_level=filters['risk_level']
                )
            
            if filters.get('payment_reliability'):
                queryset = queryset.filter(
                    customer_insights__payment_insights__payment_reliability=filters['payment_reliability']
                )
            
            if filters.get('engagement_level'):
                queryset = queryset.filter(
                    customer_insights__communication_insights__engagement_level=filters['engagement_level']
                )
            
            # Apply date filters if provided
            if filters.get('date_from') or filters.get('date_to'):
                date_filter = Q()
                if filters.get('date_from'):
                    date_filter &= Q(customer_insights__calculated_at__gte=filters['date_from'])
                if filters.get('date_to'):
                    date_filter &= Q(customer_insights__calculated_at__lte=filters['date_to'])
                queryset = queryset.filter(date_filter)
            
            # Get paginated results
            customers = queryset.distinct()[offset:offset + limit]
            
            # Build summary data
            summary_data = []
            for customer in customers:
                try:
                    insight_record = CustomerInsight.objects.get(customer=customer)
                    payment_insights = insight_record.payment_insights
                    communication_insights = insight_record.communication_insights
                    claims_insights = insight_record.claims_insights
                    profile_insights = insight_record.profile_insights
                    
                    summary_data.append({
                        'customer_id': customer.id,
                        'customer_name': customer.full_name,
                        'customer_code': customer.customer_code,
                        'total_premiums_paid': payment_insights.get('total_premiums_paid', 0),
                        'on_time_payment_rate': payment_insights.get('on_time_payment_rate', 0),
                        'total_communications': communication_insights.get('total_communications', 0),
                        'satisfaction_rating': communication_insights.get('satisfaction_rating', 0),
                        'total_claims': claims_insights.get('total_claims', 0),
                        'approval_rate': claims_insights.get('approval_rate', 0),
                        'risk_level': claims_insights.get('risk_level', 'low'),
                        'customer_segment': profile_insights.get('customer_segment', 'Standard'),
                        'last_updated': insight_record.updated_at,
                    })
                except CustomerInsight.DoesNotExist:
                    continue
            
            return Response({
                'results': summary_data,
                'count': len(summary_data),
                'limit': limit,
                'offset': offset,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to get insights summary: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='customer/(?P<case_number>[^/.]+)/payment-schedule')
    def get_payment_schedule(self, request, case_number=None):
        """Get payment schedule for a specific customer using case number"""
        try:
            # Get customer via RenewalCase using case_number
            try:
                from apps.renewals.models import RenewalCase
                renewal_case = RenewalCase.objects.select_related('customer').get(case_number=case_number)
                customer = renewal_case.customer
            except RenewalCase.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Case with number {case_number} not found',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get payment schedule using the service
            from .services import CustomerInsightsService
            service = CustomerInsightsService()
            payment_schedule_data = service.get_payment_schedule(customer)
            
            return Response({
                'success': True,
                'message': 'Payment schedule retrieved successfully',
                'data': payment_schedule_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to get payment schedule',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Detailed Communication History Endpoint
    @action(detail=False, methods=['get'], url_path='customer/(?P<case_number>[^/.]+)/communication-history')
    def get_communication_history_detail(self, request, case_number=None):
        """Get detailed communication history for a specific customer using Case Number"""
        try:
            from apps.renewals.models import RenewalCase
            # Retrieve customer via RenewalCase
            renewal_case = RenewalCase.objects.select_related('customer').get(case_number=case_number)
            customer = renewal_case.customer
            
            service = CustomerInsightsService()
            history_data = service.get_communication_history(customer)
            
            serializer = CommunicationHistoryResponseSerializer(history_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except RenewalCase.DoesNotExist:
            return Response({'error': f'Case with number {case_number} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Failed to get communication history: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- ADDED: Detailed Claims History Endpoint ---
    @action(detail=False, methods=['get'], url_path='customer/(?P<case_number>[^/.]+)/claims-history')
    def get_claims_history_detail(self, request, case_number=None):
        """Get detailed claims history for a specific customer using Case Number"""
        try:
            from apps.renewals.models import RenewalCase
            # Retrieve customer via RenewalCase
            renewal_case = RenewalCase.objects.select_related('customer').get(case_number=case_number)
            customer = renewal_case.customer

            service = CustomerInsightsService()
            history_data = service.get_claims_history(customer)
            
            serializer = ClaimsHistoryResponseSerializer(history_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except RenewalCase.DoesNotExist:
            return Response({'error': f'Case with number {case_number} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Failed to get claims history: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
