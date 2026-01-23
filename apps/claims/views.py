from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import Claim
from .serializers import (
    ClaimSerializer,
    ClaimListSerializer,
    ClaimCreateSerializer,
)

class ClaimViewSet(viewsets.ModelViewSet):
    queryset = Claim.objects.select_related(
        'customer', 
        'policy', 
        'created_by', 
        'updated_by'
    ).filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'claim_type', 'customer', 'policy']
    search_fields = [
        'claim_number', 
        'customer__first_name', 
        'customer__last_name',
        'customer__email',
        'policy_number',
        'insurance_company_name',
    ]
    ordering_fields = [
        'claim_number',
        'claim_amount',
        'status',
        'claim_type',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ClaimListSerializer
        elif self.action == 'create':
            return ClaimCreateSerializer
        return ClaimSerializer
    
    def perform_create(self, serializer):
        """Set created_by and updated_by on create"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Set updated_by on update"""
        serializer.save(updated_by=self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to return formatted response"""
        try:
            instance = self.get_object()
            serializer = ClaimSerializer(instance, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Claim retrieved successfully',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Claim not found',
                    'error': str(e)
                },
                status=status.HTTP_404_NOT_FOUND
            )
    
    def list(self, request, *args, **kwargs):
        """Override list to return formatted response"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)
                if hasattr(paginated_response, 'data'):
                    paginated_response.data['message'] = 'Claims retrieved successfully'
                return paginated_response
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(
                {
                    'success': True,
                    'message': 'Claims retrieved successfully',
                    'count': len(serializer.data),
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to retrieve claims',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        """Override create to return formatted response"""
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            response_serializer = ClaimSerializer(serializer.instance, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Claim created successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            error_message = str(e)
            error_detail = None
            
            if 'foreign key constraint' in error_message.lower():
                if 'customer_id' in error_message.lower():
                    error_detail = 'The specified customer does not exist. Please provide a valid customer_id.'
                elif 'policy_id' in error_message.lower():
                    error_detail = 'The specified policy does not exist. Please provide a valid policy_id.'
                else:
                    error_detail = 'A referenced record does not exist. Please check your foreign key references.'
            
            return Response(
                {
                    'success': False,
                    'message': 'Failed to create claim',
                    'error': error_detail if error_detail else error_message
                },
                status=status.HTTP_400_BAD_REQUEST if error_detail else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            
            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'message': 'Validation failed',
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            self.perform_update(serializer)
            
            response_serializer = ClaimSerializer(serializer.instance, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Claim updated successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to update claim',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to soft delete and return formatted response"""
        try:
            instance = self.get_object()
            instance.is_deleted = True
            instance.deleted_by = request.user
            instance.save()
            
            return Response(
                {
                    'success': True,
                    'message': 'Claim deleted successfully'
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to delete claim',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
