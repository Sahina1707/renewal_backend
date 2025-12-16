from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Avg, Count
from django.utils import timezone

from .models import (
    WhatsAppFlow, FlowBlock, WhatsAppMessageTemplate, 
    FlowTemplate, FlowAnalytics
)
from .serializers import (
    WhatsAppFlowSerializer, WhatsAppFlowDetailSerializer, 
    WhatsAppMessageTemplateSerializer, FlowTemplateSerializer
)

# --- Base ViewSet with Soft Delete and Queryset Filtering ---
class SoftDeleteModelViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that implements soft deletion and filters out deleted objects.
    """
    def get_queryset(self):
        # By default, only return records where is_deleted is False
        return super().get_queryset().filter(is_deleted=False)

    def perform_destroy(self, instance):
        # Implement Soft Delete:
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        
        # Set deleted_by user (assuming request.user is authenticated)
        user = self.request.user if self.request.user.is_authenticated else None
        instance.deleted_by = user
        
        instance.save()

# --- 1. Flow Management CRUD (Flow Management Tab) ---
class WhatsAppFlowViewSet(SoftDeleteModelViewSet):
    queryset = WhatsAppFlow.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Use detailed serializer for the flow builder canvas
        if self.action in ['retrieve', 'update', 'partial_update']:
            return WhatsAppFlowDetailSerializer
        # Use the simpler serializer for the list view (the dashboard tiles)
        return WhatsAppFlowSerializer

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        flow = self.get_object()
        if flow.status == 'DRAFT' or flow.status == 'PAUSED':
            flow.status = 'PUBLISHED'
            flow.save()
            # Add logic here to create the FlowAnalytics object if it doesn't exist
            FlowAnalytics.objects.get_or_create(flow=flow)
            return Response({'status': 'Flow published'}, status=status.HTTP_200_OK)
        return Response({'detail': 'Flow cannot be published from its current status.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        flow = self.get_object()
        flow.status = 'PAUSED'
        flow.save()
        return Response({'status': 'Flow paused'}, status=status.HTTP_200_OK)
    @action(detail=True, methods=['get'])
    def analytics_details(self, request, pk=None):
        flow = self.get_object()
        
        # --- 1. Fetch Aggregated Data from FlowAnalytics ---
        try:
            analytics = flow.analytics # Assumes OneToOne field or related_name='analytics'
        except FlowAnalytics.DoesNotExist:
            return Response({"error": "Analytics record not found for this flow."}, 
                            status=status.HTTP_404_NOT_FOUND)

        # In a real system, these calculations would be performed on logged session data.
        # For demonstration, we use existing fields in FlowAnalytics for calculation logic.
        
        # Example Calculation (using hypothetical fields that must exist in FlowAnalytics)
        total_runs = analytics.total_recipients
        completed_runs = analytics.completed_runs if hasattr(analytics, 'completed_runs') else 0
        
        # Calculate rates, avoiding division by zero
        completion_rate = (completed_runs / total_runs) * 100 if total_runs else 0
        overall_drop_off_rate = 100 - completion_rate
        
        # NOTE: avg_response_time_seconds and click_through_rate require complex logging
        # We will keep these as placeholders showing the needed field structure.
        
        # --- 2. Calculate Per-Block Drop-off Data (for Heatmap) ---
        block_analytics_list = []
        
        # Iterate over all blocks in the flow
        for block in flow.blocks.all().order_by('id'):
            block_analytics_list.append({
                "block_id": block.block_id,
                "starts": total_runs, # Should be the number of users who reached this block
                "drop_off_rate": 0.0 # Placeholder for the calculated rate
            })


        response_data = {
            "flow_id": flow.id,
            "flow_name": flow.name,
            
            "performance_summary": {
                "total_runs": total_runs,
                "completion_rate": round(completion_rate, 2),
                "avg_response_time_seconds": analytics.avg_response_time if hasattr(analytics, 'avg_response_time') else 0.0,
                "overall_drop_off_rate": round(overall_drop_off_rate, 2),
                "click_through_rate": analytics.click_through_rate if hasattr(analytics, 'click_through_rate') else 0.0
            },           
            "block_analytics": block_analytics_list,
            "report_links": {
                "csv": f"/api/flows/{flow.id}/reports/export/?type=csv",
                "pdf": f"/api/flows/{flow.id}/reports/export/?type=pdf",
                "excel": f"/api/flows/{flow.id}/reports/export/?type=excel",
                "crm_sync": f"/api/flows/{flow.id}/reports/export/?type=crm"
            }
        }
        return Response(response_data, status=status.HTTP_200_OK)
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        flow = self.get_object()    
        return Response({'status': 'Test run initiated. Check Debug Console for real-time logs.'}, 
                    status=status.HTTP_202_ACCEPTED)
    
class FlowAnalyticsReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WhatsAppFlow.objects.all() 
    serializer_class = WhatsAppFlowSerializer # Used for recent activity list items
    permission_classes = [permissions.IsAuthenticated]
    @action(detail=False, methods=['get'])
    def summary(self, request):
        metrics = FlowAnalytics.objects.aggregate(
            total_recipients=Sum('total_recipients'),
            sum_delivered=Sum('messages_delivered'),
            sum_replied=Sum('messages_replied')
        )

        total_recipients = metrics.get('total_recipients') or 0
        sum_delivered = metrics.get('sum_delivered') or 0
        sum_replied = metrics.get('sum_replied') or 0
        
        delivery_rate = (sum_delivered / total_recipients * 100) if total_recipients > 0 else 0
        reply_rate = (sum_replied / sum_delivered * 100) if sum_delivered > 0 else 0
        
        total_flows = WhatsAppFlow.objects.count()
        recent_flows = WhatsAppFlow.objects.order_by('-created_at')[:5]
        recent_activity_data = WhatsAppFlowSerializer(recent_flows, many=True).data

        response_data = {
            'total_flows': total_flows,
            'total_recipients': total_recipients,
            'delivery_rate': round(delivery_rate, 2),
            'reply_rate': round(reply_rate, 2),
            'recent_activity': recent_activity_data
        }

        return Response(response_data)

# --- 3. Templates CRUD (Templates Tab) ---
class WhatsAppMessageTemplateViewSet(SoftDeleteModelViewSet):
    queryset = WhatsAppMessageTemplate.objects.all().order_by('-created_at')
    serializer_class = WhatsAppMessageTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

class FlowTemplateViewSet(SoftDeleteModelViewSet):
    queryset = FlowTemplate.objects.all().order_by('name')
    serializer_class = FlowTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]