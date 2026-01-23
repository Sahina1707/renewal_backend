from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db.models import Q
from apps.core.pagination import StandardResultsSetPagination
from .models import CustomerVehicle
from .serializers import (
    CustomerVehicleCreateSerializer,
    CustomerVehicleListSerializer
)

class CustomerVehicleViewSet(viewsets.ModelViewSet):
    queryset = CustomerVehicle.objects.filter(is_deleted=False)
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return CustomerVehicleCreateSerializer
        return CustomerVehicleListSerializer

    def get_queryset(self):
        """Get filtered queryset for customer vehicles"""
        queryset = CustomerVehicle.objects.filter(is_deleted=False)

        # Filter by customer assets
        customer_assets_id = self.request.query_params.get('customer_assets_id')
        if customer_assets_id:
            queryset = queryset.filter(customer_assets_id=customer_assets_id)

        # Filter by customer
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_assets__customer_id=customer_id)

        # Filter by vehicle type
        vehicle_type = self.request.query_params.get('vehicle_type')
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)

        # Filter by fuel type
        fuel_type = self.request.query_params.get('fuel_type')
        if fuel_type:
            queryset = queryset.filter(fuel_type=fuel_type)

        # Filter by condition
        condition = self.request.query_params.get('condition')
        if condition:
            queryset = queryset.filter(condition=condition)

        # Filter by model year range
        min_year = self.request.query_params.get('min_year')
        max_year = self.request.query_params.get('max_year')
        if min_year:
            queryset = queryset.filter(model_year__gte=min_year)
        if max_year:
            queryset = queryset.filter(model_year__lte=max_year)

        # Filter by value range
        min_value = self.request.query_params.get('min_value')
        max_value = self.request.query_params.get('max_value')
        if min_value:
            queryset = queryset.filter(value__gte=min_value)
        if max_value:
            queryset = queryset.filter(value__lte=max_value)

        # Search by vehicle name, registration, customer name, or code
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(vehicle_name__icontains=search) |
                Q(registration_number__icontains=search) |
                Q(customer_assets__customer__first_name__icontains=search) |
                Q(customer_assets__customer__last_name__icontains=search) |
                Q(customer_assets__customer__company_name__icontains=search) |
                Q(customer_assets__customer__customer_code__icontains=search)
            )

        return queryset.select_related('customer_assets__customer').order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """List customer vehicles with success response"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response({
                    'success': True,
                    'message': 'Customer vehicles retrieved successfully',
                    'data': serializer.data
                })

            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'message': 'Customer vehicles retrieved successfully',
                'count': queryset.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving customer vehicles: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        """Store/Create new customer vehicle"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Save the customer vehicle
                customer_vehicle = serializer.save(created_by=request.user)

                # Return success response with created data
                response_serializer = CustomerVehicleListSerializer(customer_vehicle)
                return Response({
                    'success': True,
                    'message': 'Customer vehicle stored successfully',
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
                'message': f'Error storing customer vehicle: {str(e)}',
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