from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q

from .models import CustomerInstallment
from .serializers import (
    CustomerInstallmentSerializer,
    CustomerInstallmentCreateSerializer,
    CustomerInstallmentUpdateSerializer,
    OutstandingSummarySerializer,
    OutstandingInstallmentSerializer
)

class CustomerInstallmentViewSet(viewsets.ModelViewSet):
    queryset = CustomerInstallment.objects.all()
    serializer_class = CustomerInstallmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['customer', 'renewal_case', 'status', 'due_date']
    search_fields = ['customer__first_name', 'customer__last_name', 'customer__customer_code', 'renewal_case__case_number', 'period', 'payment__transaction_id']
    ordering_fields = ['due_date', 'amount', 'created_at', 'updated_at']
    ordering = ['-due_date', '-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == 'create':
            return CustomerInstallmentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CustomerInstallmentUpdateSerializer
        return CustomerInstallmentSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer=customer_id)
        
        case_id = self.request.query_params.get('renewal_case')
        if case_id:
            queryset = queryset.filter(renewal_case_id=case_id)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        due_date_from = self.request.query_params.get('due_date_from')
        due_date_to = self.request.query_params.get('due_date_to')
        
        if due_date_from:
            queryset = queryset.filter(due_date__gte=due_date_from)
        if due_date_to:
            queryset = queryset.filter(due_date__lte=due_date_to)
        
        return queryset.select_related('payment', 'customer', 'renewal_case')

    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        installment = self.get_object()
        payment_id = request.data.get('payment_id')
        
        if not payment_id:
            return Response(
                {'error': 'payment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.customer_payments.models import CustomerPayment
            payment = CustomerPayment.objects.get(id=payment_id)
            installment.mark_as_paid(payment)
            
            serializer = self.get_serializer(installment)
            return Response(serializer.data)
        except CustomerPayment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get all overdue installments"""
        overdue_installments = self.get_queryset().filter(status='overdue')
        serializer = self.get_serializer(overdue_installments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending installments"""
        pending_installments = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(pending_installments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        """Get installments by customer ID"""
        customer_id = request.query_params.get('customer')
        if not customer_id:
            return Response(
                {'error': 'customer parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        installments = self.get_queryset().filter(customer=customer_id)
        serializer = self.get_serializer(installments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_case(self, request):
        """Get installments by renewal case ID"""
        case_id = request.query_params.get('renewal_case')
        if not case_id:
            return Response(
                {'error': 'renewal_case parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        installments = self.get_queryset().filter(renewal_case_id=case_id)
        serializer = self.get_serializer(installments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def outstanding_summary(self, request):
        """Get outstanding amounts summary for a customer or case"""
        customer_id = request.query_params.get('customer')
        case_id = request.query_params.get('renewal_case')
        
        summary_data = CustomerInstallment.get_outstanding_summary(customer_id, case_id)
        
        serializer = OutstandingSummarySerializer(summary_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def outstanding_installments(self, request):
        """Get detailed outstanding installments list"""
        customer_id = request.query_params.get('customer')
        case_id = request.query_params.get('renewal_case')
        
        outstanding_installments = CustomerInstallment.get_outstanding_installments(
            customer_id, case_id
        ).select_related('customer', 'renewal_case', 'renewal_case__policy', 'renewal_case__policy__policy_type')
        
        outstanding_installments = outstanding_installments.order_by('due_date')
        
        serializer = OutstandingInstallmentSerializer(outstanding_installments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_case_outstanding(self, request):
        """Get outstanding installments for a specific case (like CASE-001)"""
        case_number = request.query_params.get('case_number')
        if not case_number:
            return Response(
                {'error': 'case_number parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.renewals.models import RenewalCase
            renewal_case = RenewalCase.objects.get(case_number=case_number)
            
            outstanding_installments = CustomerInstallment.get_outstanding_installments(
                case_id=renewal_case.id
            ).select_related('customer', 'renewal_case', 'renewal_case__policy', 'renewal_case__policy__policy_type')
            
            summary_data = CustomerInstallment.get_outstanding_summary(case_id=renewal_case.id)
            
            summary_serializer = OutstandingSummarySerializer(summary_data)
            installments_serializer = OutstandingInstallmentSerializer(outstanding_installments, many=True)
            
            return Response({
                'summary': summary_serializer.data,
                'installments': installments_serializer.data,
                'case_info': {
                    'case_number': renewal_case.case_number,
                    'customer_name': renewal_case.customer.full_name,
                    'policy_number': renewal_case.policy.policy_number
                }
            })
            
        except RenewalCase.DoesNotExist:
            return Response(
                {'error': f'Case {case_number} not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def overdue_installments(self, request):
        """Get only overdue installments (for urgent attention)"""
        customer_id = request.query_params.get('customer')
        case_id = request.query_params.get('renewal_case')
        
        overdue_installments = CustomerInstallment.get_outstanding_installments(
            customer_id, case_id
        ).filter(status='overdue').select_related('customer', 'renewal_case')
        
        overdue_installments = overdue_installments.order_by('due_date')
        
        serializer = OutstandingInstallmentSerializer(overdue_installments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def update_overdue_status(self, request):
        """Update status of pending installments that are now overdue"""
        updated_count = 0
        
        pending_installments = CustomerInstallment.objects.filter(status='pending')
        
        for installment in pending_installments:
            if installment.is_overdue():
                installment.status = 'overdue'
                installment.save(update_fields=['status'])
                updated_count += 1
        
        return Response({
            'message': f'Updated {updated_count} installments to overdue status',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'])
    def create_installments_for_policy(self, request):
        """Manually create installments for a policy"""
        policy_id = request.data.get('policy_id')
        renewal_case_id = request.data.get('renewal_case_id')
        
        if not policy_id:
            return Response(
                {'error': 'policy_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.policies.models import Policy
            from apps.renewals.models import RenewalCase
            
            policy = Policy.objects.get(id=policy_id)
            renewal_case = None
            
            if renewal_case_id:
                renewal_case = RenewalCase.objects.get(id=renewal_case_id)
            
            from .services import InstallmentIntegrationService
            result = InstallmentIntegrationService.create_installments_for_policy(
                policy, renewal_case
            )
            
            if result['success']:
                return Response(result)
            else:
                return Response(
                    {'error': result.get('error', 'Failed to create installments')}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Policy.DoesNotExist:
            return Response(
                {'error': 'Policy not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except RenewalCase.DoesNotExist:
            return Response(
                {'error': 'Renewal case not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'])
    def link_payment_to_installment(self, request):
        """Manually link a payment to an installment"""
        payment_id = request.data.get('payment_id')
        
        if not payment_id:
            return Response(
                {'error': 'payment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.customer_payments.models import CustomerPayment
            from .services import InstallmentIntegrationService
            
            payment = CustomerPayment.objects.get(id=payment_id)
            result = InstallmentIntegrationService.link_payment_to_installment(payment)
            
            if result['success']:
                return Response(result)
            else:
                return Response(
                    {'error': result.get('error', 'Failed to link payment')}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except CustomerPayment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

