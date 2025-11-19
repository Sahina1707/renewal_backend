from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Sum, Q
from celery.result import AsyncResult

# --- UPDATED IMPORTS ---
from .models import Campaign, CampaignLog, SequenceStep, PendingTask
from .serializers import CampaignSerializer, CampaignLogSerializer
from apps.audience_manager.models import Audience

# --- IMPORT NEW CELERY TASKS ---
from .tasks import process_campaign, resume_paused_campaign 

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('-created_at')
    serializer_class = CampaignSerializer
    
    # Example: You'll need to override this
    # def get_queryset(self):
    #     user = self.request.user
    #     return Campaign.objects.filter(created_by=user, is_deleted=False)

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
    
    @action(detail=False, methods=['get'], url_path='stats')
    def get_dashboard_stats(self, request):
        # queryset = self.get_queryset() # Use filtered queryset
        queryset = Campaign.objects.all() # Or all for admin

        total_campaigns = queryset.count()
        active_campaigns = queryset.filter(status=Campaign.CampaignStatus.ACTIVE).count()
        scheduled_campaigns = queryset.filter(status=Campaign.CampaignStatus.SCHEDULED).count()
        
        # --- FIX for Total Reach ---
        # We must calculate this manually as it's not a simple aggregation
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
        
        # --- THIS IS EXAMPLE LOGIC ---
        # You MUST adapt this to your provider's (e.g., SendGrid) webhook format
        
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