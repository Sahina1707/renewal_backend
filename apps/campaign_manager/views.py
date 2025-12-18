from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Sum, Q, F
from celery.result import AsyncResult
from django_filters.rest_framework import DjangoFilterBackend
from .models import Campaign, CampaignLog, SequenceStep, PendingTask
from .serializers import CampaignSerializer, CampaignLogSerializer
from apps.audience_manager.models import Audience
from .filters import CampaignFilter 
from .tasks import process_campaign, resume_paused_campaign 
import csv
import json
import io
from django.http import HttpResponse, JsonResponse

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('-created_at')
    serializer_class = CampaignSerializer
    
    # --- NEW: Filtering Setup ---
    filter_backends = [DjangoFilterBackend]
    filterset_class = CampaignFilter
    # --- END NEW ---
    
    def get_queryset(self):
        """
        Annotate the queryset with the contact count for filtering/sorting.
        """
        queryset = super().get_queryset()
        queryset = queryset.annotate(
            audience_contact_count=Count('audience__contacts')
        )
        # Example: You'll need to override this
        # user = self.request.user
        # return queryset.filter(created_by=user, is_deleted=False)
        return queryset.filter(is_deleted=False) # Filter out deleted ones

    def create(self, request, *args, **kwargs):
        """
        Create a campaign and launch it immediately if it's not scheduled.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()

        # If the campaign was created as a draft (i.e., not scheduled for the future),
        # change its status to active and start the background processing.
        if campaign.status == Campaign.CampaignStatus.DRAFT:
            campaign.status = Campaign.CampaignStatus.ACTIVE
            campaign.save(update_fields=['status'])
            process_campaign.delay(campaign_id=campaign.id)
            message = "Campaign created and is now processing."
        else:
            message = "Campaign scheduled successfully."

        headers = self.get_success_headers(serializer.data)
        return Response({'status': message, 'data': serializer.data}, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['get'], url_path='dashboard_stats')
    def get_dashboard_stats(self, request):
        # queryset = self.get_queryset() # Use filtered queryset
        queryset = Campaign.objects.all() # Or all for admin

        total_campaigns = queryset.count()
        active_campaigns = queryset.filter(status=Campaign.CampaignStatus.ACTIVE).count()
        scheduled_campaigns = queryset.filter(status=Campaign.CampaignStatus.SCHEDULED).count()
        
        total_reach = 0
        audience_ids = queryset.values_list('audience_id', flat=True).distinct()
        for aud_id in audience_ids:
            try:
                audience = Audience.objects.get(id=aud_id)
                total_reach += audience.contacts.count() # This is the correct way
            except Audience.DoesNotExist:
                continue
        return Response({
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'scheduled_campaigns': scheduled_campaigns,
            'total_reach': total_reach # Now this is correct
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='stats')
    def get_campaign_stats(self, request, pk=None):
        campaign = self.get_object()
        serializer = self.get_serializer(campaign)
        return Response(serializer.data.get('log_counts'))

    @action(detail=True, methods=['post'], url_path='resume')
    def resume_campaign(self, request, pk=None):
        """
        This is the "Launch" button.
        It handles starting a DRAFT or resuming a PAUSED campaign.
        """
        campaign = self.get_object()
        
        # --- UPDATED (Bug Fix) ---
        if campaign.status == Campaign.CampaignStatus.DRAFT:
            # This is a NEW launch
            campaign.status = Campaign.CampaignStatus.ACTIVE
            campaign.save()
            process_campaign.delay(campaign_id=campaign.id)
            return Response(
                {'status': 'Campaign is now active and processing.'}, 
                status=status.HTTP_200_OK
            )
        
        elif campaign.status == Campaign.CampaignStatus.PAUSED:
            # This is RESUMING a paused campaign
            campaign.status = Campaign.CampaignStatus.ACTIVE
            campaign.save()
            resume_paused_campaign.delay(campaign_id=campaign.id) # <-- Call NEW task
            return Response(
                {'status': 'Campaign is resuming.'}, 
                status=status.HTTP_200_OK
            )
        # --- END OF UPDATE ---
        
        return Response(
            {'error': 'Campaign is already active or completed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'], url_path='pause')
    def pause_campaign(self, request, pk=None):
        """
        This is the "Pause" button.
        It finds and revokes all pending Celery tasks.
        """
        campaign = self.get_object()
        
        if campaign.status != Campaign.CampaignStatus.ACTIVE:
            return Response({'error': 'Campaign is not active.'}, status=status.HTTP_400_BAD_REQUEST)

        campaign.status = Campaign.CampaignStatus.PAUSED
        campaign.save()
        
        # This is the actual "pause" logic
        pending_tasks = PendingTask.objects.filter(campaign=campaign)
        revoked_count = 0
        for task in pending_tasks:
            try:
                AsyncResult(task.task_id).revoke(terminate=True)
                revoked_count += 1
            except Exception as e:
                print(f"Could not revoke task {task.task_id}: {e}")
        
        # We leave the tasks in the DB to be resumed later
        # pending_tasks.delete() 
        
        return Response({'status': f'Campaign paused. {revoked_count} pending tasks cancelled.'})
    
    @action(detail=False, methods=['get'], url_path='export')
    def export_campaigns(self, request):
        """
        Handles exporting campaigns to CSV or JSON, based on current filters.
        Includes robust, binary-safe CSV encoding fix.
        """
        # Robust parsing: handle None, strip whitespace, lowercase
        export_format = request.query_params.get('format', '').lower().strip()
        
        if not export_format:
            return Response(
                {'error': 'Export format must be explicitly specified via the "format" query parameter (e.g., ?format=csv).'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        export_data_scope = request.query_params.get('scope', 'filtered').lower()
            
        # Get the queryset, applying active filters from the request
        queryset = self.filter_queryset(self.get_queryset())
        
        # If user chose "All Campaigns", reset queryset
        if export_data_scope == 'all':
            queryset = Campaign.objects.filter(is_deleted=False).annotate(
                audience_contact_count=Count('audience__contacts')
            )
        
        # 2. Get Serialized Data and Campaign Objects
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        campaign_objects = {c.id: c for c in queryset}        
        def get_export_row(item):
            campaign_id = item.get('id')
            if campaign_id is None:
                return ["Error: Missing ID"]
                
            campaign = None
            try:
                # Ensure we cast to INT for the dictionary lookup
                c_id_int = int(campaign_id)
                campaign = campaign_objects.get(c_id_int) 
            except (ValueError, TypeError):
                pass

            # Use explicit variables for readability and safety
            # Use getattr/hasattr to avoid crashes if display methods are missing
            campaign_type_display = item.get('campaign_type', '')
            if campaign and hasattr(campaign, 'get_campaign_type_display'):
                campaign_type_display = campaign.get_campaign_type_display()
            
            status_display = item.get('status', '')
            if campaign and hasattr(campaign, 'get_status_display'):
                status_display = campaign.get_status_display()
            
            # NOTE: All values are cast to str() for maximum safety against TypeErrors
            return [
                str(campaign_id), 
                str(item.get('name', 'N/A')), 
                str(campaign_type_display), 
                str(status_display),
                str(item.get('audience_name', 'N/A')),
                str(item.get('total_contacts', 0)),
                str(item.get('created_at', 'N/A')),
            ]
        
        headers = [
            'ID', 'Name', 'Type', 'Status', 'Audience Name', 'Total Contacts',
            'Created At',
        ]
        
        filename_base = f'campaigns_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}'

        # 3. Handle CSV Export (Using BytesIO for guaranteed UTF-8 encoding)
        if export_format == 'csv':
            buffer = io.BytesIO()
            # Use utf-8-sig for Excel compatibility
            text_wrapper = io.TextIOWrapper(buffer, encoding='utf-8-sig', newline='')
            writer = csv.writer(text_wrapper)

            # Write header
            writer.writerow(headers)

            for item in data:
                try:
                    writer.writerow(get_export_row(item))
                except Exception as e:
                    print(f"FATAL EXCEPTION DURING CSV ROW WRITE for ID {item.get('id')}: {e}")
                    return Response(
                         {'error': f"CSV Generation Failed for Campaign ID {item.get('id')}: {str(e)}"}, 
                         status=status.HTTP_500_INTERNAL_SERVER_ERROR
                     )
            
            # Flush and get content
            text_wrapper.flush()
            
            # Use the simplest possible HttpResponse creation
            response = HttpResponse(
                buffer.getvalue(), 
                content_type='text/csv; charset=utf-8'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
            
            return response
        
        # 4. Handle JSON Export
        elif export_format == 'json':
            return JsonResponse(
                data, 
                safe=False, 
                json_dumps_params={'indent': 4},
                content_type='application/json',
                headers={'Content-Disposition': f'attachment; filename="{filename_base}.json"'}
            )

        # 5. Handle Unsupported Formats (XLSX, PDF) 
        elif export_format in ['xlsx', 'excel', 'pdf', 'pdf report']:
            return Response(
                {'error': f'Unsupported export format: {export_format}. This format requires additional backend libraries to be installed and configured.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 6. Handle Unknown Format
        else:
            return Response(
                {'error': f'Unknown export format: {export_format}. Supported formats are CSV and JSON.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class CampaignLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CampaignLog.objects.all().order_by('-sent_at')
    serializer_class = CampaignLogSerializer
    filterset_fields = ['campaign', 'contact', 'status', 'step']

class WebhookReceiverView(generics.GenericAPIView):
    """
    A new, un-authenticated endpoint for your email/SMS provider
    to send status updates (Delivered, Opened, Clicked).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        print("--- WEBHOOK RECEIVED ---")
        print(data)
        
        try:
            # 1. Find the log by the provider's ID
            message_id = data.get('message_id') # Example field
            event_type = data.get('event') # Example field
            
            log = CampaignLog.objects.filter(message_provider_id=message_id).first()
            if not log:
                return Response({'status': 'Log not found'}, status=status.HTTP_404_NOT_FOUND)

            # 2. Update the status based on the event
            if event_type == 'delivered':
                log.status = CampaignLog.LogStatus.DELIVERED
            elif event_type == 'open':
                log.status = CampaignLog.LogStatus.OPENED
            elif event_type == 'click':
                log.status = CampaignLog.LogStatus.CLICKED
            elif event_type == 'bounce' or event_type == 'failed':
                log.status = CampaignLog.LogStatus.FAILED
                log.error_message = data.get('reason', 'Webhook failure')
            
            log.save()
            
            return Response({'status': 'received'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Webhook Error: {e}")
            return Response({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)