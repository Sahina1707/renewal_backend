# pyright: reportAttributeAccessIssue=false
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import DistributionChannel
from .serializers import (
    DistributionChannelSerializer,
    DistributionChannelListSerializer,
    DistributionChannelCreateSerializer,
)

class DistributionChannelViewSet(viewsets.ModelViewSet):
    queryset = DistributionChannel.objects.select_related('channel', 'created_by', 'updated_by').filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['channel_type', 'status', 'region', 'channel']
    search_fields = ['name', 'description', 'contact_person', 'contact_email', 'region']
    ordering_fields = ['name', 'channel_type', 'status', 'commission_rate', 'target_revenue', 'partner_since', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DistributionChannelListSerializer
        elif self.action == 'create':
            return DistributionChannelCreateSerializer
        return DistributionChannelSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to return formatted response"""
        try:
            instance = self.get_object()
            serializer = DistributionChannelSerializer(instance, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel retrieved successfully',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Distribution channel not found',
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
                # Add message to paginated response
                if hasattr(paginated_response, 'data'):
                    paginated_response.data['message'] = 'Distribution channels retrieved successfully'
                return paginated_response
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(
                {
                    'success': True,
                    'message': 'Distribution channels retrieved successfully',
                    'count': len(serializer.data),
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to retrieve distribution channels',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        """Override create to return formatted response"""
        serializer = self.get_serializer(data=request.data)
        
        # Validate data
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save the instance
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            # Return formatted response with full serializer data
            response_serializer = DistributionChannelSerializer(serializer.instance, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel created successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to create distribution channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        """Set created_by when creating a new distribution channel"""
        serializer.save(created_by=self.request.user)
    
    def update(self, request, *args, **kwargs):
        """Override update to return formatted response"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        # Validate data
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save the instance
        try:
            self.perform_update(serializer)
            
            # Return formatted response with full serializer data
            response_serializer = DistributionChannelSerializer(serializer.instance, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel updated successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to update distribution channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_update(self, serializer):
        """Set updated_by when updating a distribution channel"""
        serializer.save(updated_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to return formatted response"""
        try:
            instance = self.get_object()
            channel_name = instance.name
            channel_type = instance.channel_type
            channel_id = instance.id
            
            self.perform_destroy(instance)
            
            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel deleted successfully',
                    'data': {
                        'id': channel_id,
                        'name': channel_name,
                        'channel_type': channel_type,
                        'deleted_by': request.user.username if request.user else None,
                        'deletion_type': 'soft_delete'
                    }
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to delete distribution channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_destroy(self, instance):
        """Perform soft delete"""
        instance.delete(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active distribution channels"""
        active_channels = self.get_queryset().filter(status='Active')
        serializer = self.get_serializer(active_channels, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get distribution channels by type"""
        channel_type = request.query_params.get('type')
        if not channel_type:
            return Response(
                {'error': 'Channel type parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        channels = self.get_queryset().filter(channel_type=channel_type)
        serializer = self.get_serializer(channels, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a distribution channel"""
        channel = self.get_object()
        channel.status = 'Active'
        channel.updated_by = request.user
        channel.save()
        
        serializer = self.get_serializer(channel)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a distribution channel"""
        channel = self.get_object()
        channel.status = 'Inactive'
        channel.updated_by = request.user
        channel.save()
        
        serializer = self.get_serializer(channel)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get distribution channel statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_channels': queryset.count(),
            'active_channels': queryset.filter(status='Active').count(),
            'inactive_channels': queryset.filter(status='Inactive').count(),
            'pending_channels': queryset.filter(status='Pending').count(),
            'by_type': {},
            'by_region': {}
        }
        
        # Count by channel type
        for choice in DistributionChannel.CHANNEL_TYPE_CHOICES:
            channel_type = choice[0]
            count = queryset.filter(channel_type=channel_type).count()
            stats['by_type'][channel_type] = count
        
        # Count by region
        regions = queryset.exclude(region__isnull=True).exclude(region='').values_list('region', flat=True).distinct()
        for region in regions:
            count = queryset.filter(region=region).count()
            stats['by_region'][region] = count
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def create_channel(self, request):
        """Create a new distribution channel with formatted response"""
        serializer = DistributionChannelCreateSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            channel = serializer.save(created_by=request.user)
            response_serializer = DistributionChannelSerializer(channel, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel created successfully',
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def list_all_channels(self, request):
        """List all distribution channels with formatted response"""
        try:
            channels = self.get_queryset()
            serializer = DistributionChannelSerializer(channels, many=True, context={'request': request})

            return Response(
                {
                    'success': True,
                    'message': 'Distribution channels retrieved successfully',
                    'count': channels.count(),
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to retrieve distribution channels',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def get_channel_by_id(self, request):
        """Get a specific distribution channel by ID"""
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Distribution channel ID is required',
                        'error': 'Please provide channel ID as query parameter: ?id=1'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel = self.get_queryset().get(id=channel_id)
            except DistributionChannel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Distribution channel not found',
                        'error': f'Distribution channel with ID {channel_id} does not exist'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = DistributionChannelSerializer(channel, context={'request': request})

            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel retrieved successfully',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to retrieve distribution channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['put'])
    def edit_channel(self, request):
        """Update a distribution channel with formatted response"""
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Distribution channel ID is required',
                        'error': 'Please provide channel ID as query parameter: ?id=1'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel = self.get_queryset().get(id=channel_id)
            except DistributionChannel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Distribution channel not found',
                        'error': f'Distribution channel with ID {channel_id} does not exist'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            update_data = request.data.copy()

            serializer = DistributionChannelSerializer(
                channel,
                data=update_data,
                partial=True,
                context={'request': request}
            )

            if serializer.is_valid():
                updated_channel = serializer.save(updated_by=request.user)
                response_serializer = DistributionChannelSerializer(updated_channel, context={'request': request})
                return Response(
                    {
                        'success': True,
                        'message': 'Distribution channel updated successfully',
                        'data': response_serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        'success': False,
                        'message': 'Validation failed',
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to update distribution channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'])
    def delete_channel(self, request):
        """Delete a distribution channel with formatted response"""
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Distribution channel ID is required',
                        'error': 'Please provide channel ID as query parameter: ?id=1'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel_id = int(channel_id)
            except (ValueError, TypeError):
                return Response(
                    {
                        'success': False,
                        'message': 'Invalid distribution channel ID',
                        'error': 'Distribution channel ID must be a valid integer'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel = self.get_queryset().get(id=channel_id)
            except DistributionChannel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Distribution channel not found',
                        'error': f'Distribution channel with ID {channel_id} does not exist or has already been deleted'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            channel_name = channel.name
            channel_type = channel.channel_type

            channel.hard_delete()

            return Response(
                {
                    'success': True,
                    'message': 'Distribution channel deleted successfully',
                    'data': {
                        'id': channel_id,
                        'name': channel_name,
                        'channel_type': channel_type,
                        'deleted_by': request.user.username if request.user else None,
                        'deletion_type': 'hard_delete'
                    }
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to delete distribution channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
