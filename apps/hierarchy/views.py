from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q

from .models import HierarchyManagement
from .serializers import (
    HierarchyManagementSerializer,
    HierarchyManagementCreateSerializer,
    HierarchyManagementListSerializer
)


class HierarchyManagementViewSet(viewsets.ModelViewSet):
    queryset = HierarchyManagement.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['unit_type', 'parent_unit', 'status', 'manager_id']
    search_fields = ['unit_name', 'description', 'manager_id']
    ordering_fields = ['unit_name', 'unit_type', 'created_at', 'budget', 'target_cases']
    ordering = ['unit_type', 'unit_name']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return HierarchyManagementCreateSerializer
        elif self.action == 'list':
            return HierarchyManagementListSerializer
        return HierarchyManagementSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
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
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # Use List serializer for response
        instance = serializer.instance
        response_serializer = HierarchyManagementListSerializer(instance, context={'request': request})

        response_data = {
            'success': True,
            'message': 'Hierarchy unit created successfully',
            'data': response_serializer.data
        }
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Use List serializer for response
        response_serializer = HierarchyManagementListSerializer(instance, context={'request': request})

        response_data = {
            'success': True,
            'message': 'Hierarchy unit updated successfully',
            'data': response_serializer.data
        }
        return Response(response_data)
    
    def perform_destroy(self, instance):
        # Store info before deletion for response
        self.deleted_unit_info = {
            'id': instance.id,
            'unit_name': instance.unit_name,
            'unit_type': instance.unit_type
        }
        # Perform hard delete - permanently remove from database
        instance.hard_delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)

        response_data = {
            'success': True,
            'message': 'Hierarchy unit deleted permanently from database'
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            # Wrap paginated response with success format
            response_data = {
                'success': True,
                'message': 'Hierarchy units retrieved successfully',
                'data': paginated_response.data
            }
            return Response(response_data)

        serializer = self.get_serializer(queryset, many=True)
        response_data = {
            'success': True,
            'message': 'Hierarchy units retrieved successfully',
            'data': serializer.data,
            'count': len(serializer.data)
        }
        return Response(response_data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        response_data = {
            'success': True,
            'message': 'Hierarchy unit retrieved successfully',
            'data': serializer.data
        }
        return Response(response_data)

    @action(detail=False, methods=['get'])
    def choices(self, request):
        # Get actual parent units from database
        parent_units_list = []
        
        # Add "None (Root Level)" option
        parent_units_list.append({
            'value': 'none',
            'display': 'None (Root Level)'
        })
        
        # Get all active hierarchy units as potential parent units
        available_parents = self.get_queryset().filter(status='active').order_by('unit_type', 'unit_name')
        for unit in available_parents:
            # Create a slug-like value from unit_name to match the model's choice format
            parent_value = unit.unit_name.lower().replace(' ', '_').replace('-', '_')
            parent_units_list.append({
                'value': parent_value,
                'display': f"{unit.unit_name} ({unit.get_unit_type_display()})"
            })
        
        choices_data = {
            'unit_types': [
                {'value': choice[0], 'display': choice[1]}
                for choice in HierarchyManagement.UNIT_TYPE_CHOICES
            ],
            'parent_units': parent_units_list,
            'statuses': [
                {'value': choice[0], 'display': choice[1]}
                for choice in HierarchyManagement.STATUS_CHOICES
            ]
        }

        response_data = {
            'success': True,
            'message': 'Hierarchy choices retrieved successfully',
            'data': choices_data
        }
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        unit_type = request.query_params.get('type')
        if not unit_type:
            return Response(
                {'error': 'type parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        units = self.get_queryset().filter(unit_type=unit_type)
        serializer = HierarchyManagementListSerializer(units, many=True)

        response_data = {
            'success': True,
            'message': f'Hierarchy units of type "{unit_type}" retrieved successfully',
            'data': serializer.data,
            'count': len(serializer.data)
        }
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def by_parent(self, request):
        parent_unit = request.query_params.get('parent')
        if not parent_unit:
            return Response(
                {'error': 'parent parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        units = self.get_queryset().filter(parent_unit=parent_unit)
        serializer = HierarchyManagementListSerializer(units, many=True)

        response_data = {
            'success': True,
            'message': f'Hierarchy units under parent "{parent_unit}" retrieved successfully',
            'data': serializer.data,
            'count': len(serializer.data)
        }
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        
        stats = {
            'total_units': queryset.count(),
            'by_type': {},
            'by_status': {},
            'by_parent': {},
            'total_budget': 0,
            'total_target_cases': 0
        }
        
        # Count by unit type
        for unit_type, display in HierarchyManagement.UNIT_TYPE_CHOICES:
            count = queryset.filter(unit_type=unit_type).count()
            stats['by_type'][unit_type] = {'count': count, 'display': display}
        
        # Count by status
        for status_choice, display in HierarchyManagement.STATUS_CHOICES:
            count = queryset.filter(status=status_choice).count()
            stats['by_status'][status_choice] = {'count': count, 'display': display}
        
        # Count by parent unit
        for parent_unit, display in HierarchyManagement.PARENT_UNIT_CHOICES:
            count = queryset.filter(parent_unit=parent_unit).count()
            stats['by_parent'][parent_unit] = {'count': count, 'display': display}
        
        # Calculate totals
        stats['total_budget'] = sum(
            unit.budget for unit in queryset if unit.budget
        )
        stats['total_target_cases'] = sum(
            unit.target_cases for unit in queryset
        )

        response_data = {
            'success': True,
            'message': 'Hierarchy statistics retrieved successfully',
            'data': stats
        }
        return Response(response_data)
