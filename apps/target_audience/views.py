from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from .models import TargetAudience
from .serializers import (
    TargetAudienceSerializer,
    TargetAudienceListSerializer,
    TargetAudienceCreateSerializer
)


class TargetAudienceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing target audiences"""
    
    queryset = TargetAudience.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TargetAudienceListSerializer
        elif self.action == 'create':
            return TargetAudienceCreateSerializer
        return TargetAudienceSerializer
    
    def get_queryset(self):
        """Filter target audiences based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by search term
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(key__icontains=search)
            )
        
        return queryset.order_by('name')
    
    @action(detail=False, methods=['get'])
    def options(self, request):
        """Get target audience options for dropdowns"""
        audiences = self.get_queryset()
        serializer = TargetAudienceListSerializer(audiences, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def predefined(self, request):
        """Get predefined target audience options (for campaign creation)"""
        predefined_options = [
            {
                'id': 'all_customers',
                'name': 'All Customers',
                'description': 'Target all customers in the uploaded file'
            },
            {
                'id': 'pending_renewals',
                'name': 'Pending Renewals Only',
                'description': 'Target customers with policies due for renewal'
            },
            {
                'id': 'expired_policies', 
                'name': 'Expired Policies Only',
                'description': 'Target customers with expired policies'
            }
        ]
        return Response(predefined_options)
