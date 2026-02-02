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
    filter_backends = [DjangoFilterBackend]
    filterset_class = CampaignFilter
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.annotate(
            audience_contact_count=Count('audience__contacts')
        )
        return queryset.filter(is_deleted=False)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
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
        queryset = Campaign.objects.all()

        total_campaigns = queryset.count()
        active_campaigns = queryset.filter(status=Campaign.CampaignStatus.ACTIVE).count()
        scheduled_campaigns = queryset.filter(status=Campaign.CampaignStatus.SCHEDULED).count()
        
        total_reach = 0
        audience_ids = queryset.values_list('audience_id', flat=True).distinct()
        for aud_id in audience_ids:
            try:
                audience = Audience.objects.get(id=aud_id)
                total_reach += audience.contacts.count()
            except Audience.DoesNotExist:
                continue
        return Response({
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'scheduled_campaigns': scheduled_campaigns,
            'total_reach': total_reach 
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='stats')
    def get_campaign_stats(self, request, pk=None):
        campaign = self.get_object()
        serializer = self.get_serializer(campaign)
        return Response(serializer.data.get('log_counts'))

    @action(detail=True, methods=['post'], url_path='resume')
    def resume_campaign(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status == Campaign.CampaignStatus.DRAFT:
            campaign.status = Campaign.CampaignStatus.ACTIVE
            campaign.save()
            process_campaign.delay(campaign_id=campaign.id)
            return Response(
                {'status': 'Campaign is now active and processing.'}, 
                status=status.HTTP_200_OK
            )
        
        elif campaign.status == Campaign.CampaignStatus.PAUSED:
            campaign.status = Campaign.CampaignStatus.ACTIVE
            campaign.save()
            resume_paused_campaign.delay(campaign_id=campaign.id) 
            return Response(
                {'status': 'Campaign is resuming.'}, 
                status=status.HTTP_200_OK
            )
        return Response(
            {'error': 'Campaign is already active or completed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'], url_path='pause')
    def pause_campaign(self, request, pk=None):
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
        
        return Response({'status': f'Campaign paused. {revoked_count} pending tasks cancelled.'})
    
    @action(detail=False, methods=['get'], url_path='export')
    def export_campaigns(self, request):
        export_format = request.query_params.get('format', '').lower().strip()
        
        if not export_format:
            return Response(
                {'error': 'Export format must be explicitly specified via the "format" query parameter (e.g., ?format=csv).'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        export_data_scope = request.query_params.get('scope', 'filtered').lower()
            
        queryset = self.filter_queryset(self.get_queryset())
        
        if export_data_scope == 'all':
            queryset = Campaign.objects.filter(is_deleted=False).annotate(
                audience_contact_count=Count('audience__contacts')
            )
        
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        campaign_objects = {c.id: c for c in queryset}        
        def get_export_row(item):
            campaign_id = item.get('id')
            if campaign_id is None:
                return ["Error: Missing ID"]
                
            campaign = None
            try:
                c_id_int = int(campaign_id)
                campaign = campaign_objects.get(c_id_int) 
            except (ValueError, TypeError):
                pass
            campaign_type_display = item.get('campaign_type', '')
            if campaign and hasattr(campaign, 'get_campaign_type_display'):
                campaign_type_display = campaign.get_campaign_type_display()
            
            status_display = item.get('status', '')
            if campaign and hasattr(campaign, 'get_status_display'):
                status_display = campaign.get_status_display()
            
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

        if export_format == 'csv':
            buffer = io.BytesIO()
            text_wrapper = io.TextIOWrapper(buffer, encoding='utf-8-sig', newline='')
            writer = csv.writer(text_wrapper)

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
            
            text_wrapper.flush()
            
            response = HttpResponse(
                buffer.getvalue(), 
                content_type='text/csv; charset=utf-8'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
            
            return response
        
        elif export_format == 'json':
            return JsonResponse(
                data, 
                safe=False, 
                json_dumps_params={'indent': 4},
                content_type='application/json',
                headers={'Content-Disposition': f'attachment; filename="{filename_base}.json"'}
            )

        elif export_format in ['xlsx', 'excel', 'pdf', 'pdf report']:
            return Response(
                {'error': f'Unsupported export format: {export_format}. This format requires additional backend libraries to be installed and configured.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
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
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        print("--- WEBHOOK RECEIVED ---")
        print(data)
        
        try:
            message_id = data.get('message_id') 
            event_type = data.get('event')
            
            log = CampaignLog.objects.filter(message_provider_id=message_id).first()
            if not log:
                return Response({'status': 'Log not found'}, status=status.HTTP_404_NOT_FOUND)

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