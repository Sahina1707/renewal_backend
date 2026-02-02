from rest_framework import status, viewsets
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from .models import CustomerPayment
from .serializers import (
    CustomerPaymentSerializer,
    CustomerPaymentCreateSerializer,
    CustomerPaymentUpdateSerializer,
    CustomerPaymentListSerializer
)
class CustomerPaymentViewSet(viewsets.ModelViewSet):
    queryset = CustomerPayment.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerPaymentCreateSerializer
        elif self.action == 'list':
            return CustomerPaymentListSerializer
        elif self.action in ['update', 'partial_update']:
            return CustomerPaymentUpdateSerializer
        return CustomerPaymentSerializer

    def get_queryset(self):
        queryset = CustomerPayment.objects.filter(is_deleted=False)

        renewal_case_id = self.request.query_params.get('renewal_case_id')
        if renewal_case_id:
            queryset = queryset.filter(renewal_case_id=renewal_case_id)

        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(renewal_case__customer_id=customer_id)

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        payment_mode = self.request.query_params.get('payment_mode')
        if payment_mode:
            queryset = queryset.filter(payment_mode=payment_mode)

        payment_gateway = self.request.query_params.get('payment_gateway')
        if payment_gateway:
            queryset = queryset.filter(payment_gateway=payment_gateway)

        currency = self.request.query_params.get('currency')
        if currency:
            queryset = queryset.filter(currency=currency)

        is_auto_payment = self.request.query_params.get('is_auto_payment')
        if is_auto_payment is not None:
            queryset = queryset.filter(is_auto_payment=is_auto_payment.lower() == 'true')

        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            queryset = queryset.filter(payment_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(payment_amount__lte=max_amount)

        # Filter by payment date range
        payment_from = self.request.query_params.get('payment_from')
        payment_to = self.request.query_params.get('payment_to')
        if payment_from:
            queryset = queryset.filter(payment_date__gte=payment_from)
        if payment_to:
            queryset = queryset.filter(payment_date__lte=payment_to)

        # Filter by due date range
        due_from = self.request.query_params.get('due_from')
        due_to = self.request.query_params.get('due_to')
        if due_from:
            queryset = queryset.filter(due_date__gte=due_from)
        if due_to:
            queryset = queryset.filter(due_date__lte=due_to)

        # Filter overdue payments
        overdue_only = self.request.query_params.get('overdue_only')
        if overdue_only and overdue_only.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                due_date__lt=today,
                payment_status__in=['pending', 'failed']
            )

        # Filter successful payments
        successful_only = self.request.query_params.get('successful_only')
        if successful_only and successful_only.lower() == 'true':
            queryset = queryset.filter(payment_status='completed')

        # Filter failed payments
        failed_only = self.request.query_params.get('failed_only')
        if failed_only and failed_only.lower() == 'true':
            queryset = queryset.filter(payment_status__in=['failed', 'cancelled'])

        # Filter pending payments
        pending_only = self.request.query_params.get('pending_only')
        if pending_only and pending_only.lower() == 'true':
            queryset = queryset.filter(payment_status__in=['pending', 'processing'])

        # Filter refunded payments
        refunded_only = self.request.query_params.get('refunded_only')
        if refunded_only and refunded_only.lower() == 'true':
            queryset = queryset.filter(
                Q(payment_status='refunded') | Q(refund_amount__gt=0)
            )

        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(transaction_id__icontains=search) |
                Q(reference_number__icontains=search) |
                Q(receipt_number__icontains=search) |
                Q(renewal_case__customer__first_name__icontains=search) |
                Q(renewal_case__customer__last_name__icontains=search) |
                Q(renewal_case__customer__customer_code__icontains=search) |
                Q(renewal_case__case_number__icontains=search) |
                Q(renewal_case__policy__policy_number__icontains=search)
            )

        return queryset.select_related(
            'renewal_case',
            'renewal_case__customer',
            'renewal_case__policy'
        ).order_by('-payment_date', '-created_at')

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                customer_payment = serializer.save(created_by=request.user)

                response_serializer = CustomerPaymentSerializer(customer_payment)
                return Response({
                    'success': True,
                    'message': 'Customer payment stored successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error storing customer payment: {str(e)}',
                'errors': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)

            return Response({
                'success': True,
                'message': 'Customer payments retrieved successfully',
                'count': queryset.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving customer payments: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        """Create customer payment"""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Update customer payment"""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete the customer payment"""
        instance.delete(user=self.request.user)
