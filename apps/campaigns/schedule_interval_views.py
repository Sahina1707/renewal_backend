from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.http import Http404
from .models import Campaign, CampaignScheduleInterval
from .serializers import (
    CampaignScheduleIntervalSerializer,
    CampaignScheduleIntervalCreateSerializer,
    CampaignScheduleIntervalUpdateSerializer
)

class CampaignScheduleIntervalViewSet(viewsets.ModelViewSet):
    """ViewSet for managing campaign schedule intervals"""
    
    queryset = CampaignScheduleInterval.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign', 'channel', 'is_active', 'is_sent']
    search_fields = ['campaign__name', 'template__name', 'communication_provider__name']
    ordering_fields = ['sequence_order', 'scheduled_at', 'created_at']
    ordering = ['campaign', 'sequence_order']
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CampaignScheduleIntervalCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CampaignScheduleIntervalUpdateSerializer
        return CampaignScheduleIntervalSerializer
    
    def get_queryset(self):
        """Filter queryset based on campaign parameter and exclude deleted records"""
        queryset = CampaignScheduleInterval.objects.filter(is_deleted=False)
        campaign_id = self.request.query_params.get('campaign_id')
        
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Override create to add success message"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response({
            'success': True,
            'message': 'Campaign schedule interval created successfully!',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Override update to add success message"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'success': True,
            'message': 'Campaign schedule interval updated successfully!',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to add success message"""
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return Response({
            'success': True,
            'message': 'Campaign schedule interval deleted successfully!'
        }, status=status.HTTP_200_OK)
    
    def list(self, request, *args, **kwargs):
        """Override list to add success message"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data.update({
                'success': True,
                'message': f'Retrieved {len(serializer.data)} schedule interval(s) successfully!'
            })
            return paginated_response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': f'Retrieved {len(serializer.data)} schedule interval(s) successfully!',
            'data': serializer.data
        })
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to add success message"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response({
            'success': True,
            'message': 'Campaign schedule interval retrieved successfully!',
            'data': serializer.data
        })
    
    def perform_create(self, serializer):
        """Set created_by user"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by user"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the interval"""
        instance.soft_delete(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a schedule interval"""
        interval = self.get_object()
        interval.is_active = True
        interval.updated_by = request.user
        interval.save()
        
        serializer = self.get_serializer(interval)
        return Response({
            'success': True,
            'message': f'Schedule interval {interval.sequence_order} activated successfully!',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a schedule interval"""
        interval = self.get_object()
        interval.is_active = False
        interval.updated_by = request.user
        interval.save()
        
        serializer = self.get_serializer(interval)
        return Response({
            'success': True,
            'message': f'Schedule interval {interval.sequence_order} deactivated successfully!',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        """Mark a schedule interval as sent"""
        interval = self.get_object()
        interval.is_sent = True
        interval.sent_at = timezone.now()
        interval.updated_by = request.user
        interval.save()
        
        serializer = self.get_serializer(interval)
        return Response({
            'success': True,
            'message': f'Schedule interval {interval.sequence_order} marked as sent!',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def by_campaign(self, request):
        """Get all schedule intervals for a specific campaign"""
        campaign_id = request.query_params.get('campaign_id')
        if not campaign_id:
            return Response({
                'success': False,
                'message': 'campaign_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, is_deleted=False)
            intervals = self.get_queryset().filter(campaign=campaign).order_by('sequence_order')
            serializer = self.get_serializer(intervals, many=True)
            
            return Response({
                'success': True,
                'message': f'Retrieved {len(serializer.data)} schedule intervals for campaign "{campaign.name}"',
                'data': serializer.data
            })
        except Campaign.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Campaign not found'
            }, status=status.HTTP_404_NOT_FOUND)