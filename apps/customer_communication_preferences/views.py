from rest_framework import status, viewsets
from rest_framework.response import Response
from django.db.models import Q
from apps.core.pagination import StandardResultsSetPagination
from .models import CustomerCommunicationPreference
from .serializers import (
    CustomerCommunicationPreferenceCreateSerializer,
    CustomerCommunicationPreferenceListSerializer
)

class CustomerCommunicationPreferenceViewSet(viewsets.ModelViewSet):
    queryset = CustomerCommunicationPreference.objects.filter(is_deleted=False)
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return CustomerCommunicationPreferenceCreateSerializer
        elif self.action == 'list':
            return CustomerCommunicationPreferenceListSerializer
        return CustomerCommunicationPreferenceListSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = self.queryset.select_related('customer')
        
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        communication_type = self.request.query_params.get('communication_type')
        if communication_type:
            queryset = queryset.filter(communication_type=communication_type)
        
        preferred_channel = self.request.query_params.get('preferred_channel')
        if preferred_channel:
            queryset = queryset.filter(preferred_channel=preferred_channel)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__email__icontains=search) |
                Q(customer__customer_code__icontains=search) |
                Q(communication_type__icontains=search) |
                Q(preferred_channel__icontains=search)
            )
        
        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new customer communication preference"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                communication_preference = serializer.save(created_by=request.user)
                
                response_serializer = CustomerCommunicationPreferenceListSerializer(communication_preference)
                
                return Response({
                    'success': True,
                    'message': 'Customer communication preference created successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error creating customer communication preference: {str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request, *args, **kwargs):
        """List customer communication preferences"""
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)
                
                return Response({
                    'success': True,
                    'message': 'Customer communication preferences retrieved successfully',
                    'count': queryset.count(),
                    'data': paginated_response.data
                }, status=status.HTTP_200_OK)
            
            serializer = self.get_serializer(queryset, many=True)
            
            return Response({
                'success': True,
                'message': 'Customer communication preferences retrieved successfully',
                'count': queryset.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving customer communication preferences: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        """Set created_by when creating"""
        serializer.save(created_by=self.request.user)
