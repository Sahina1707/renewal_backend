from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from apps.renewals.models import RenewalCase
from apps.core.pagination import StandardResultsSetPagination
from .serializers import ClosedCasesListSerializer, ClosedCasesDetailSerializer
from datetime import datetime, timedelta
from django.utils import timezone
from apps.files_upload.models import FileUpload


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
            'policy',                     
            'policy__policy_type',        
            'channel_id',                 
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
            queryset = queryset.filter(channel_id__channel_name__icontains=channel)
        
        # Agent filter
        agent = request.query_params.get('agent', None)
        if agent:
            queryset = queryset.filter(
                Q(assigned_to__first_name__icontains=agent) |
                Q(assigned_to__last_name__icontains=agent) |
                Q(assigned_to__username__icontains=agent)
            )
        
        # Date range filters
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
        
        # Batch ID filter
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
            'channel_id__name'
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
