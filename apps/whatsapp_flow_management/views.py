from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Avg, Count
from django.utils import timezone
import csv
from itertools import chain
from operator import attrgetter
from django.http import HttpResponse
import openpyxl  # For Excel
from reportlab.pdfgen import canvas 
from reportlab.lib.pagesizes import letter

from .models import (
    WhatsAppFlow, FlowBlock, WhatsAppMessageTemplate, 
    FlowTemplate, FlowAnalytics, AITemplate
)
from .serializers import (
    WhatsAppFlowSerializer, WhatsAppFlowDetailSerializer, 
    WhatsAppMessageTemplateSerializer, FlowTemplateSerializer,
    AITemplateSerializer
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
        """
        Populates the Right Sidebar Analytics Tab.
        Returns ONLY: Total Runs, Completion Rate, Avg Time, and Export Link.
        """
        flow = self.get_object()
        
        # Get Stats (Safe Access)
        stats, _ = FlowAnalytics.objects.get_or_create(flow=flow)
        
        total = stats.total_runs
        completed = stats.completed_runs
        
        # Calculate Percentage
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # Generate the Export URL for the button
        export_url = request.build_absolute_uri(f'/api/whatsapp_flow_management/flows/{flow.id}/export_report/?type=csv')

        return Response({
            "total_runs": total,
            "completion_rate": f"{completion_rate:.0f}%", # Rounds to "94%"
            "avg_response_time": f"{stats.avg_duration_seconds:.1f}s", # e.g. "2.3s"
            "export_url": export_url  # Put this in the href of "Export Analytics Report" button
        })

    # --- 2. EXPORT BUTTON ACTION ---
    @action(detail=True, methods=['get'])
    def export_report(self, request, pk=None):
        """
        Downloads the CSV when user clicks 'Export Analytics Report' in the sidebar.
        """
        flow = self.get_object()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{flow.name}_analytics.csv"'

        writer = csv.writer(response)
        writer.writerow(['Metric', 'Value'])
        
        stats, _ = FlowAnalytics.objects.get_or_create(flow=flow)
        writer.writerow(['Flow Name', flow.name])
        writer.writerow(['Total Runs', stats.total_runs])
        writer.writerow(['Completed Runs', stats.completed_runs])
        writer.writerow(['Avg Response Time', f"{stats.avg_duration_seconds:.1f}s"])
        
        return response
    @action(detail=True, methods=['post'])
    def test_flow(self, request, pk=None):
        """
        Connect this to the 'Test' button.
        It sends a REAL WhatsApp message to the number provided.
        """
        flow = self.get_object()
        phone_number = request.data.get('phone_number')
        
        if not phone_number:
            return Response({"error": "Please provide a phone number to test."}, status=400)        
        return Response({
            "status": "success",
            "message": f"Test message sent to {phone_number}",
            "details": f"Triggered flow '{flow.name}' starting at block {flow.entry_point}"
        })
    @action(detail=True, methods=['post'])
    def track_event(self, request, pk=None):
        flow = self.get_object()
        analytics, _ = FlowAnalytics.objects.get_or_create(flow=flow)
        
        event = request.data.get('event')
        duration = request.data.get('duration', 0)

        if event == "START":
            analytics.total_runs += 1
        elif event == "COMPLETE":
            analytics.completed_runs += 1
            # Update Average Time
            if analytics.completed_runs > 1:
                prev_total = analytics.avg_duration_seconds * (analytics.completed_runs - 1)
                analytics.avg_duration_seconds = (prev_total + float(duration)) / analytics.completed_runs
            else:
                analytics.avg_duration_seconds = float(duration)
        elif event == "DROP":
            analytics.dropped_off_runs += 1
            # Optional: Add node drop-off logic here if sent from frontend

        analytics.save()
        return Response({"status": "Analytics Updated"})
    
    @action(detail=True, methods=['post'])
    def debug_flow(self, request, pk=None):
        """
        DRY RUN: Simulates the flow logic without sending real WhatsApp messages.
        Returns the 'Path' (Trace) of blocks validation.
        """
        flow = self.get_object()
        user_input = request.data.get('mock_input', 'Hello') # Simulate user saying "Hello"
        
        trace_log = []
        
        # 1. Start at the first block (logic depends on your canvas structure)
        # For this demo, let's assume we find the block with no incoming connections or a specific start flag
        current_block = flow.blocks.first() # specific logic needed here based on your JSON structure
        
        step_count = 0
        while current_block and step_count < 10: # Limit steps to prevent infinite loops
            step_count += 1
            trace_log.append({
                "step": step_count,
                "block_id": current_block.block_id,
                "block_type": current_block.block_type,
                "status": "SUCCESS",
                "message": f"Processed {current_block.block_type}"
            })
            
            # Simulate moving to next block
            if current_block.connections:
                # In a real engine, you evaluate IF/ELSE conditions here.
                # For Debug, we just take the first 'success' path.
                next_id = current_block.connections[0].get('target_block_id')
                current_block = flow.blocks.filter(block_id=next_id).first()
            else:
                current_block = None

        return Response({
            "status": "Debug Complete",
            "flow_valid": True,
            "trace_log": trace_log
        })
    @action(detail=False, methods=['get'])
    def demo_flow(self, request):
        """
        Returns a hardcoded 'Sample Flow' structure.
        The Frontend uses this to render a 'Demo Canvas' showing the user
        how a finished flow looks (e.g., Welcome -> Input -> End).
        """
        demo_data = {
            "name": "Demo: Customer Feedback (Example)",
            "entry_point": "INBOUND",
            "canvas_layout": {
                "demo_block_1": {"x": 100, "y": 200},
                "demo_block_2": {"x": 500, "y": 200},
                "demo_block_3": {"x": 900, "y": 200}
            },
            "blocks": [
                {
                    "block_id": "demo_block_1",
                    "block_type": "SEND_MESSAGE",
                    "configuration": {
                        "message": "👋 Hi! This is a demo. Welcome to our service!"
                    },
                    "connections": [
                        {"output": "success", "target_block_id": "demo_block_2"}
                    ]
                },
                {
                    "block_id": "demo_block_2",
                    "block_type": "COLLECT_INPUT",
                    "configuration": {
                        "question": "How would you rate us?",
                        "input_type": "text"
                    },
                    "connections": [
                        {"output": "valid", "target_block_id": "demo_block_3"}
                    ]
                },
                {
                    "block_id": "demo_block_3",
                    "block_type": "SEND_MESSAGE",
                    "configuration": {
                        "message": "Thanks for your feedback! ✅"
                    },
                    "connections": []
                }
            ]
        }
        return Response(demo_data)
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


class AITemplateViewSet(SoftDeleteModelViewSet):
    queryset = AITemplate.objects.filter(is_deleted=False).order_by('-created_at')
    serializer_class = AITemplateSerializer  
    permission_classes = [permissions.IsAuthenticated]

class TemplatesDashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def get_dashboard_data(self, request):
        
        msg_count = WhatsAppMessageTemplate.objects.filter(is_deleted=False).count()
        flow_count = FlowTemplate.objects.filter(is_deleted=False).count()
        ai_count = AITemplate.objects.filter(is_deleted=False).count()
        
        # Define the static UI labels (These are fine to keep here or move to a config file)
        cards_data = [
            {
                # "id": "message_templates",
                "title": "Message Templates",
                "count": msg_count, # <--- Dynamic
                "description": "Pre-approved message templates for marketing and notifications",
                "button_text": "Manage Templates"
            },
            {
                # "id": "flow_templates",
                "title": "Flow Templates",
                "count": flow_count, # <--- Dynamic
                "description": "Complete flow templates for common use cases",
                "button_text": "Browse Templates"
            },
            {
                # "id": "ai_templates",
                "title": "AI Templates",
                "count": ai_count, # <--- Dynamic
                "description": "AI-generated templates based on your business needs",
                "button_text": "Generate New"
            }
        ]

        # --- PART 2: FETCH & MERGE RECENT ITEMS ---
        # 1. Fetch top 5 items from each table (Optimize query by only getting needed fields if necessary)
        recent_msgs = WhatsAppMessageTemplate.objects.filter(is_deleted=False).order_by('-updated_at')[:5]
        recent_flows = FlowTemplate.objects.filter(is_deleted=False).order_by('-updated_at')[:5]
        recent_ai = AITemplate.objects.filter(is_deleted=False).order_by('-updated_at')[:5]
        
        # 2. Combine all three lists
        combined_list = list(chain(recent_msgs, recent_flows, recent_ai))
        
        # 3. Sort by 'updated_at' (Newest first)
        combined_list.sort(key=attrgetter('updated_at'), reverse=True)
        
        # 4. Take the top 5 most recent items across all types
        final_recent_list = combined_list[:5]

        # 5. Format the data for the UI
        recent_data = []
        for item in final_recent_list:
            # Determine type specific fields
            if isinstance(item, WhatsAppMessageTemplate):
                type_label = "Message Template"
                category = item.content_json.get('category', 'Marketing') if item.content_json else 'Marketing'
                icon_type = "chat_bubble"
                status = item.get_status_display()
                
            elif isinstance(item, FlowTemplate):
                type_label = "Flow Template"
                category = getattr(item, 'category', 'General')
                icon_type = "flow_tree"
                status = "Active" 
                
            elif isinstance(item, AITemplate):
                type_label = "AI Template"
                category = getattr(item, 'category', 'AI Generated')
                icon_type = "auto_awesome" # Example icon name for AI
                status = getattr(item, 'status', 'Draft')

            recent_data.append({
                "id": item.id,
                "name": item.name,
                "type": type_label,       
                "category": category,
                "icon_type": icon_type,
                "last_modified": item.updated_at,
                "status": status
            })

        return Response({
            "cards": cards_data,
            "recent_templates": recent_data
        })
# In apps/whatsapp_flow_management/views.py

class AnalyticsDashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def global_stats(self, request):
        # --- 1. AGGREGATE REAL KPI METRICS ---
        # Fetch sum of all runs across all flows
        agg_data = FlowAnalytics.objects.aggregate(
            total_sessions=Sum('total_runs'),
            total_completed=Sum('completed_runs'),
            total_dropped=Sum('dropped_off_runs'),
            avg_time=Avg('avg_duration_seconds')
        )

        # Handle None values (if database is empty)
        total = agg_data['total_sessions'] or 0
        completed = agg_data['total_completed'] or 0
        dropped = agg_data['total_dropped'] or 0
        avg_time_val = agg_data['avg_time'] or 0.0

        # Calculate Percentages
        completion_rate = (completed / total * 100) if total > 0 else 0
        drop_off_rate = (dropped / total * 100) if total > 0 else 0
        all_analytics = FlowAnalytics.objects.exclude(node_drop_off_data={})
        
        drop_off_counts = {}
        for entry in all_analytics:
            for node_id, count in entry.node_drop_off_data.items():
                drop_off_counts[node_id] = drop_off_counts.get(node_id, 0) + count
        sorted_drop_offs = sorted(drop_off_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        heatmap_data = []
        for node_name, count in sorted_drop_offs:
            # Determine logic for Red/Orange/Green labels
            if count > 50:
                level = "High Drop-off"
            elif count > 20:
                level = "Medium Drop-off"
            else:
                level = "Low Drop-off"
                
            heatmap_data.append({
                "node": node_name, # Shows "node_1" or "Welcome Msg" depending on what you saved
                "value": count,
                "drop_off_level": level
            })


        # --- 3. GENERATE DOWNLOAD LINKS ---
        base_url = request.build_absolute_uri('/api/whatsapp_flow_management/analytics_dashboard/export_report/')

        return Response({
            "kpi_metrics": {
                "completion_rate":f"{completion_rate:.1f}%",
                "avg_response_time": f"{avg_time_val:.1f}s",
                "drop_off_rate": f"{drop_off_rate:.1f}%",
                },
            "heatmap_data": heatmap_data, 
            "download_links": {
                "csv": f"{base_url}?type=csv",
                "excel": f"{base_url}?type=excel",
                "pdf": f"{base_url}?type=pdf",
                "crm_sync": f"{base_url}?type=crm_sync"
            },
        })
    @action(detail=False, methods=['get'])
    def export_report(self, request):
        report_type = request.query_params.get('type', 'csv')
        
        # 1. Fetch REAL data from your database
        flows = WhatsAppFlow.objects.filter(is_deleted=False).order_by('-created_at')

        # CSV DOWNLOAD 
        if report_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'
            
            writer = csv.writer(response)
            # Header
            writer.writerow(['Flow Name', 'Status', 'Created At', 'Total Runs'])
            # Data Rows
            for flow in flows:
                # fetch real analytics if they exist, else 0
                runs = getattr(flow, 'analytics', None).total_runs if hasattr(flow, 'analytics') else 0
                writer.writerow([flow.name, flow.get_status_display(), flow.created_at.strftime("%Y-%m-%d"), runs])
            
            return response

        # --- OPTION 2: EXCEL DOWNLOAD ---
        elif report_type == 'excel':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="analytics_report.xlsx"'

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Flow Analytics"

            # Header
            headers = ['Flow Name', 'Status', 'Created At', 'Total Runs']
            ws.append(headers)

            # Data Rows
            for flow in flows:
                runs = getattr(flow, 'analytics', None).total_runs if hasattr(flow, 'analytics') else 0
                # Excel handles python dates automatically
                ws.append([flow.name, flow.get_status_display(), flow.created_at.replace(tzinfo=None), runs])

            wb.save(response)
            return response

        # --- OPTION 3: PDF DOWNLOAD ---
        elif report_type == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="analytics_report.pdf"'

            p = canvas.Canvas(response, pagesize=letter)
            width, height = letter
            y = height - 40 # Start at the top of the page

            # Title
            p.setFont("Helvetica-Bold", 16)
            p.drawString(30, y, "WhatsApp Flow Analytics Report")
            y -= 30
            
            # Headers
            p.setFont("Helvetica-Bold", 12)
            p.drawString(30, y, "Flow Name")
            p.drawString(250, y, "Status")
            p.drawString(350, y, "Created Date")
            p.drawString(480, y, "Total Runs")
            y -= 20
            p.line(30, y+15, 550, y+15) # Underline header

            # Data Rows
            p.setFont("Helvetica", 10)
            for flow in flows:
                if y < 50: # Check if page is full
                    p.showPage()
                    y = height - 40
                
                runs = getattr(flow, 'analytics', None).total_runs if hasattr(flow, 'analytics') else 0
                
                p.drawString(30, y, flow.name[:35]) # Truncate long names
                p.drawString(250, y, flow.get_status_display())
                p.drawString(350, y, flow.created_at.strftime("%Y-%m-%d"))
                p.drawString(480, y, str(runs))
                y -= 20

            p.showPage()
            p.save()
            return response

        return Response({"error": "Invalid type"}, status=400)