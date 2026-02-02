from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import CustomerPolicyPreference
from .serializers import (
    CustomerPolicyPreferenceSerializer,
    CustomerPolicyPreferenceCreateSerializer,
    CustomerPolicyPreferenceListSerializer
)

class CustomerPolicyPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Customer Policy Preferences with store and list functionality.
    """
    queryset = CustomerPolicyPreference.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'store':
            return CustomerPolicyPreferenceCreateSerializer
        elif self.action == 'list':
            return CustomerPolicyPreferenceListSerializer
        return CustomerPolicyPreferenceSerializer

    def get_queryset(self):
        """Get filtered queryset based on query parameters"""
        queryset = CustomerPolicyPreference.objects.filter(is_deleted=False)

        # Filter by customer
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Filter by renewal case
        renewal_case_id = self.request.query_params.get('renewal_case_id')
        if renewal_case_id:
            queryset = queryset.filter(renewal_cases_id=renewal_case_id)

        # Filter by coverage type
        coverage_type = self.request.query_params.get('coverage_type')
        if coverage_type:
            queryset = queryset.filter(coverage_type=coverage_type)

        # Filter by payment mode
        payment_mode = self.request.query_params.get('payment_mode')
        if payment_mode:
            queryset = queryset.filter(payment_mode=payment_mode)

        # Filter by preferred insurer
        preferred_insurer = self.request.query_params.get('preferred_insurer')
        if preferred_insurer:
            queryset = queryset.filter(preferred_insurer__icontains=preferred_insurer)

        # Filter by auto renewal preference
        auto_renewal = self.request.query_params.get('auto_renewal')
        if auto_renewal is not None:
            queryset = queryset.filter(auto_renewal=auto_renewal.lower() == 'true')

        # Filter by communication preference
        communication_preference = self.request.query_params.get('communication_preference')
        if communication_preference:
            queryset = queryset.filter(communication_preference=communication_preference)

        # Search by customer name, code, or insurer
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__company_name__icontains=search) |
                Q(customer__customer_code__icontains=search) |
                Q(preferred_insurer__icontains=search) |
                Q(special_requirements__icontains=search)
            )

        return queryset.select_related('customer', 'renewal_cases').order_by('-created_at')

    @action(detail=False, methods=['post'])
    def store(self, request):
        try:
            serializer = CustomerPolicyPreferenceCreateSerializer(data=request.data)
            if serializer.is_valid():
                policy_preference = serializer.save(created_by=request.user)

                response_serializer = CustomerPolicyPreferenceSerializer(policy_preference)
                return Response({
                    'success': True,
                    'message': 'Customer policy preference stored successfully',
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
                'message': f'Error storing customer policy preference: {str(e)}',
                'errors': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request):
        try:
            # Get filtered queryset
            preferences = self.get_queryset()

            # Serialize the data
            serializer = CustomerPolicyPreferenceListSerializer(preferences, many=True)

            return Response({
                'success': True,
                'message': 'Customer policy preferences retrieved successfully',
                'count': preferences.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving customer policy preferences: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


