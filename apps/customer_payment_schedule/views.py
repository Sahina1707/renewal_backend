
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from apps.core.pagination import StandardResultsSetPagination
from .models import PaymentSchedule
from .serializers import (
    PaymentScheduleCreateSerializer,
    PaymentScheduleListSerializer,
)


class CustomerPaymentScheduleViewSet(viewsets.ModelViewSet):
   
    queryset = PaymentSchedule.objects.filter(is_deleted=False)
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentScheduleCreateSerializer
        return PaymentScheduleListSerializer

    def get_queryset(self):
        queryset = PaymentSchedule.objects.filter(is_deleted=False)

        renewal_case_id = self.request.query_params.get('renewal_case_id')
        if renewal_case_id:
            queryset = queryset.filter(renewal_case_id=renewal_case_id)

        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(renewal_case__customer_id=customer_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        auto_payment = self.request.query_params.get('auto_payment')
        if auto_payment is not None:
            queryset = queryset.filter(auto_payment_enabled=auto_payment.lower() == 'true')

        due_from = self.request.query_params.get('due_from')
        due_to = self.request.query_params.get('due_to')
        if due_from:
            queryset = queryset.filter(due_date__gte=due_from)
        if due_to:
            queryset = queryset.filter(due_date__lte=due_to)

        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            queryset = queryset.filter(amount_due__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(amount_due__lte=max_amount)

        installment_number = self.request.query_params.get('installment_number')
        if installment_number:
            queryset = queryset.filter(installment_number=installment_number)

        overdue_only = self.request.query_params.get('overdue_only')
        if overdue_only and overdue_only.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                due_date__lt=today,
                status__in=['pending', 'scheduled', 'failed']
            )

        due_today = self.request.query_params.get('due_today')
        if due_today and due_today.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(due_date=today)

        upcoming_days = self.request.query_params.get('upcoming_days')
        if upcoming_days:
            try:
                days = int(upcoming_days)
                today = timezone.now().date()
                future_date = today + timedelta(days=days)
                queryset = queryset.filter(
                    due_date__gte=today,
                    due_date__lte=future_date,
                    status__in=['pending', 'scheduled']
                )
            except ValueError:
                pass

        completed_only = self.request.query_params.get('completed_only')
        if completed_only and completed_only.lower() == 'true':
            queryset = queryset.filter(status='completed')

        failed_only = self.request.query_params.get('failed_only')
        if failed_only and failed_only.lower() == 'true':
            queryset = queryset.filter(status='failed')

        pending_only = self.request.query_params.get('pending_only')
        if pending_only and pending_only.lower() == 'true':
            queryset = queryset.filter(status__in=['pending', 'scheduled'])

        payment_gateway = self.request.query_params.get('payment_gateway')
        if payment_gateway:
            queryset = queryset.filter(payment_gateway=payment_gateway)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(transaction_reference__icontains=search) |
                Q(renewal_case__customer__first_name__icontains=search) |
                Q(renewal_case__customer__last_name__icontains=search) |
                Q(renewal_case__customer__customer_code__icontains=search) |
                Q(renewal_case__case_number__icontains=search) |
                Q(renewal_case__policy__policy_number__icontains=search) |
                Q(description__icontains=search)
            )

        return queryset.select_related(
            'renewal_case',
            'renewal_case__customer',
            'renewal_case__policy'
        ).order_by('due_date', 'installment_number')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response({
                    'success': True,
                    'message': 'Customer payment schedules retrieved successfully',
                    'data': serializer.data
                })

            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'message': 'Customer payment schedules retrieved successfully',
                'count': queryset.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving customer payment schedules: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                payment_schedule = serializer.save(created_by=request.user)

                response_serializer = PaymentScheduleListSerializer(payment_schedule)
                return Response({
                    'success': True,
                    'message': 'Customer payment schedule stored successfully',
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
                'message': f'Error storing customer payment schedule: {str(e)}',
                'errors': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        return Response({
            'success': False,
            'message': 'Retrieve action not available'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        return Response({
            'success': False,
            'message': 'Update action not available'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response({
            'success': False,
            'message': 'Partial update action not available'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response({
            'success': False,
            'message': 'Delete action not available'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)
