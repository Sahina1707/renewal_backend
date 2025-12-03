from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Sum
from .models import CustomerFile
from .serializers import (
    CustomerFileSerializer,
    CustomerFileListSerializer
)
from apps.core.pagination import StandardResultsSetPagination


class CustomerFileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing customer files"""

    queryset = CustomerFile.objects.select_related(
        'uploaded_by', 'updated_by', 'customer'
    ).filter(is_active=True)

    serializer_class = CustomerFileSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # Filter fields
    filterset_fields = [
        'customer', 'file_type', 'uploaded_by', 'is_active'
    ]

    # Search fields
    search_fields = [
        'file_name', 'file_type'
    ]
    
    # Ordering fields
    ordering_fields = [
        'uploaded_at', 'updated_at', 'file_name', 'file_size'
    ]
    ordering = ['-uploaded_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return CustomerFileListSerializer
        return CustomerFileSerializer
    
    def perform_create(self, serializer):
        """Set uploaded_by when creating a new customer file"""
        serializer.save(uploaded_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating a customer file"""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Perform a soft delete by deactivating the file."""
        instance.is_active = False
        instance.updated_by = self.request.user
        instance.save()
    
    def create(self, request, *args, **kwargs):
        """Create a new customer file"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response({
            'success': True,
            'message': 'Customer file uploaded successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def list(self, request, *args, **kwargs):
        """List all customer files with filtering and pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'success': True,
                'message': 'Customer files retrieved successfully',
                'data': serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Customer files retrieved successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        """Get all files for a specific customer"""
        customer_id = request.query_params.get('customer_id')

        if not customer_id:
            return Response({
                'success': False,
                'message': 'Customer ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        files = self.get_queryset().filter(customer=customer_id)
        serializer = CustomerFileListSerializer(files, many=True)

        # Calculate statistics
        stats = files.aggregate(
            total_files=Count('id'),
            total_size=Sum('file_size')
        )

        return Response({
            'success': True,
            'message': 'Customer files retrieved successfully',
            'data': serializer.data,
            'statistics': stats
        })

    @action(detail=True, methods=['patch'])
    def deactivate(self, request, pk=None):
        """Deactivate a customer file"""
        file_instance = self.get_object()
        file_instance.is_active = False
        file_instance.updated_by = request.user
        file_instance.save()
        
        return Response({
            'success': True,
            'message': 'Customer file deactivated successfully'
        })
    
    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        """Activate a customer file"""
        file_instance = self.get_object()
        file_instance.is_active = True
        file_instance.updated_by = request.user
        file_instance.save()
        
        return Response({
            'success': True,
            'message': 'Customer file activated successfully'
        })
