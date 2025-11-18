# pyright: reportAttributeAccessIssue=false
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import Channel
from .serializers import (
    ChannelSerializer,
    ChannelListSerializer,
    ChannelCreateSerializer,
    ChannelCreateAPISerializer
)


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.select_related('target_audience').filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['channel_type', 'status', 'priority', 'manager_name', 'target_audience']
    search_fields = ['name', 'description', 'manager_name']
    ordering_fields = ['name', 'channel_type', 'status', 'priority', 'created_at', 'cost_per_lead', 'budget']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ChannelListSerializer
        elif self.action == 'create':
            return ChannelCreateSerializer
        return ChannelSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        instance.delete(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        active_channels = self.get_queryset().filter(status='active')
        serializer = self.get_serializer(active_channels, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
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
        """Activate a channel"""
        channel = self.get_object()
        channel.status = 'active'
        channel.updated_by = request.user
        channel.save()
        
        serializer = self.get_serializer(channel)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a channel"""
        channel = self.get_object()
        channel.status = 'inactive'
        channel.updated_by = request.user
        channel.save()
        
        serializer = self.get_serializer(channel)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get channel statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_channels': queryset.count(),
            'active_channels': queryset.filter(status='active').count(),
            'inactive_channels': queryset.filter(status='inactive').count(),
            'maintenance_channels': queryset.filter(status='maintenance').count(),
            'by_type': {},
            'by_priority': {}
        }
        
        # Count by channel type
        for choice in Channel.CHANNEL_TYPE_CHOICES:
            channel_type = choice[0]
            count = queryset.filter(channel_type=channel_type).count()
            stats['by_type'][channel_type] = count
        
        # Count by priority
        for choice in Channel.PRIORITY_CHOICES:
            priority = choice[0]
            count = queryset.filter(priority=priority).count()
            stats['by_priority'][priority] = count
        
        return Response(stats)

    @action(detail=False, methods=['post'])
    def create_channel(self, request):
        serializer = ChannelCreateAPISerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            # Respect provided status/priority; fall back to model defaults
            channel = serializer.save(
                created_by=request.user
            )

            # Return the created channel data
            response_serializer = ChannelCreateAPISerializer(channel, context={'request': request})
            return Response(
                {
                    'success': True,
                    'message': 'Channel created successfully',
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
       
        try:
            channels = self.get_queryset()
            serializer = ChannelCreateAPISerializer(channels, many=True, context={'request': request})

            return Response(
                {
                    'success': True,
                    'message': 'Channels retrieved successfully',
                    'count': channels.count(),
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to retrieve channels',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def get_channel_by_id(self, request):
        
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel ID is required',
                        'error': 'Please provide channel ID as query parameter: ?id=1'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel = self.get_queryset().get(id=channel_id)
            except Channel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel not found',
                        'error': f'Channel with ID {channel_id} does not exist'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = ChannelCreateAPISerializer(channel, context={'request': request})

            return Response(
                {
                    'success': True,
                    'message': 'Channel retrieved successfully',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to retrieve channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['put'])
    def edit_channel(self, request):
    
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel ID is required',
                        'error': 'Please provide channel ID as query parameter: ?id=1'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel = self.get_queryset().get(id=channel_id)
            except Channel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel not found',
                        'error': f'Channel with ID {channel_id} does not exist'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Use request data directly since ID is now in query params
            update_data = request.data.copy()

            serializer = ChannelCreateAPISerializer(
                channel,
                data=update_data,
                partial=True,  # Allow partial updates
                context={'request': request}
            )

            if serializer.is_valid():
                # Update the channel with updated_by field
                updated_channel = serializer.save(updated_by=request.user)

                # Return the updated channel data
                response_serializer = ChannelCreateAPISerializer(updated_channel, context={'request': request})
                return Response(
                    {
                        'success': True,
                        'message': 'Channel updated successfully',
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
                    'message': 'Failed to update channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['put'], url_path='edit/(?P<channel_id>[^/.]+)')
    def edit_channel_by_id(self, request, channel_id=None):
        try:
            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel ID is required',
                        'error': 'Please provide channel ID in URL path'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Convert to int to ensure proper type
                channel_id = int(channel_id)
            except (ValueError, TypeError):
                return Response(
                    {
                        'success': False,
                        'message': 'Invalid channel ID',
                        'error': 'Channel ID must be a valid integer'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                channel = self.get_queryset().get(id=channel_id)
            except Channel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel not found',
                        'error': f'Channel with ID {channel_id} does not exist'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Use request data directly since ID is now in URL path
            update_data = request.data.copy()

            serializer = ChannelCreateAPISerializer(
                channel,
                data=update_data,
                partial=True,  # Allow partial updates
                context={'request': request}
            )

            if serializer.is_valid():
                # Update the channel with updated_by field
                updated_channel = serializer.save(updated_by=request.user)

                # Return the updated channel data
                response_serializer = ChannelCreateAPISerializer(updated_channel, context={'request': request})
                return Response(
                    {
                        'success': True,
                        'message': 'Channel updated successfully',
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
                    'message': 'Failed to update channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def check_channel_status(self, request):
       
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel ID is required',
                        'error': 'Please provide channel ID as query parameter'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Check if channel exists (including deleted ones)
                channel = Channel.objects.get(id=channel_id)

                return Response(
                    {
                        'success': True,
                        'message': 'Channel status retrieved',
                        'data': {
                            'id': int(channel_id),
                            'name': channel.name,
                            'channel_type': channel.channel_type,
                            'is_deleted': channel.is_deleted,
                            'deleted_at': channel.deleted_at,
                            'deleted_by': channel.deleted_by.username if channel.deleted_by else None,
                            'status': 'deleted' if channel.is_deleted else 'active'
                        }
                    },
                    status=status.HTTP_200_OK
                )

            except Channel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel not found',
                        'error': f'Channel with ID {channel_id} does not exist in database'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to check channel status',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'])
    def delete_channel(self, request):
       
        try:
            channel_id = request.query_params.get('id')

            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel ID is required',
                        'error': 'Please provide channel ID as query parameter: ?id=1'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Convert to int to ensure proper type
                channel_id = int(channel_id)
            except (ValueError, TypeError):
                return Response(
                    {
                        'success': False,
                        'message': 'Invalid channel ID',
                        'error': 'Channel ID must be a valid integer'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Check if channel exists (only active channels)
                channel = self.get_queryset().get(id=channel_id)

            except Channel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel not found',
                        'error': f'Channel with ID {channel_id} does not exist or has already been deleted'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Store channel info before deletion for response
            channel_name = channel.name
            channel_type = channel.channel_type

            # Perform hard delete - permanently remove from database
            channel.hard_delete()

            return Response(
                {
                    'success': True,
                    'message': 'Channel deleted sccessfully',
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
                    'message': 'Failed to delete channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'], url_path='delete/(?P<channel_id>[^/.]+)')
    def delete_channel_by_id(self, request, channel_id=None):
       
        try:
            if not channel_id:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel ID is required',
                        'error': 'Please provide channel ID in URL path'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Convert to int to ensure proper type
                channel_id = int(channel_id)
            except (ValueError, TypeError):
                return Response(
                    {
                        'success': False,
                        'message': 'Invalid channel ID',
                        'error': 'Channel ID must be a valid integer'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Check if channel exists (only active channels)
                channel = self.get_queryset().get(id=channel_id)

            except Channel.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Channel not found',
                        'error': f'Channel with ID {channel_id} does not exist or has already been deleted'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            channel_name = channel.name
            channel_type = channel.channel_type

            channel.hard_delete()

            return Response(
                {
                    'success': True,
                    'message': 'Channel deleted sccessfully',
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
                    'message': 'Failed to delete channel',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=False, methods=['get', 'post'])
    def manager_names(self, request):
        if request.method == 'GET':
            managers = (
                Channel.objects
                .filter(is_deleted=False)
                .exclude(manager_name__isnull=True)
                .exclude(manager_name__exact='')
                .values_list('manager_name', flat=True)
                .distinct()
            )

            return Response(
                {'success': True, 'managers': list(managers)},
                status=status.HTTP_200_OK
            )

        if request.method == 'POST':
            manager_name = request.data.get('manager_name', '').strip()

            if not manager_name:
                return Response(
                    {'success': False, 'error': 'Manager name cannot be empty'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            exists = Channel.objects.filter(manager_name__iexact=manager_name).exists()
            if exists:
                return Response(
                    {'success': True, 'message': 'Manager already exists', 'manager_name': manager_name},
                    status=status.HTTP_200_OK
                )

            Channel.objects.create(
                name=f"Temp-{manager_name}",
                channel_type='Online',
                manager_name=manager_name,
                created_by=request.user
            )

            return Response(
                {'success': True, 'message': 'Manager created successfully', 'manager_name': manager_name},
                status=status.HTTP_201_CREATED
            )

        


