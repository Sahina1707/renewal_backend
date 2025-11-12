# File: apps/campaign_manager/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

# --- IMPORT EVERYTHING WE NEED ---
from .models import Campaign, CampaignLog, SequenceStep
from .serializers import CampaignSerializer, CampaignLogSerializer

# --- IMPORT THE CELERY TASK ---
from .tasks import process_campaign

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('-created_at')
    serializer_class = CampaignSerializer
    # permission_classes = [permissions.IsAuthenticated] 

    def get_queryset(self):
        # ... (your filter logic) ...
        return super().get_queryset()

    @action(detail=True, methods=['post'], url_path='resume')
    def resume_campaign(self, request, pk=None):
        """
        MODIFIED TO BE SYNCHRONOUS (NO CELERY).
        This function now does all the work directly and will wait until it's done.
        """
        campaign = self.get_object()
        
        if campaign.status in [Campaign.CampaignStatus.DRAFT, Campaign.CampaignStatus.PAUSED]:
            campaign.status = Campaign.CampaignStatus.ACTIVE
            campaign.save()
            
            # --- SYNCHRONOUS EXECUTION ---
            # We call the helper method directly. The request will hang until this is done.
            self._send_campaign_sync(campaign)
            
            return Response(
                {'status': 'Emails are sent safely in the background.'}, 
                status=status.HTTP_200_OK
            )

        # --- ASYNCHRONOUS (CELERY) VERSION - COMMENTED OUT ---
        # if campaign.status in [Campaign.CampaignStatus.DRAFT, Campaign.CampaignStatus.PAUSED]:
        #     # 1. Update the state
        #     campaign.status = Campaign.CampaignStatus.ACTIVE
        #     campaign.save()
            
        #     # 2. --- THIS IS THE ONLY JOB NOW ---
        #     # Hand off the work to Celery (the "kitchen")
        #     process_campaign.delay(campaign_id=campaign.id)
            
        #     # 3. Respond IMMEDIATELY
        #     return Response(
        #         {'status': 'Campaign is now active and processing in the background.'}, 
        #         status=status.HTTP_200_OK
        #     )
        
        return Response(
            {'error': 'Campaign is already active or completed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    def _send_campaign_sync(self, campaign):
        """
        Synchronous helper to process a campaign, replacing Celery tasks.
        """
        from .helpers import send_smtp_email
        from apps.audience_manager.models import AudienceContact
        import time

        contacts = campaign.audience.contacts.all()
        if not contacts.exists():
            campaign.status = Campaign.CampaignStatus.COMPLETED
            campaign.save()
            return

        all_steps = sorted(list(campaign.cm_sequence_steps.all()), key=lambda s: s.step_order)
        if not all_steps:
            return

        for contact in contacts:
            for i, step in enumerate(all_steps):
                # --- Handle Delay ---
                if i > 0:
                    delay_in_seconds = (step.delay_days * 86400) + (step.delay_hours * 3600)
                    time.sleep(delay_in_seconds)

                # --- Check Trigger Condition ---
                if step.trigger_condition == 'no_response':
                    if CampaignLog.objects.filter(campaign=campaign, contact=contact, status=CampaignLog.LogStatus.REPLIED).exists():
                        # Stop sequence for this contact if they replied
                        break 

                # --- Process Channel (EMAIL ONLY)
                success = False
                error_msg = None
                if step.channel == 'email' and contact.email:
                    template = step.template
                    success, error_msg = send_smtp_email(template.subject, template.content, contact.email)
                else:
                    error_msg = "Contact has no email or channel is not email."

                # --- Log the Result ---
                CampaignLog.objects.create(
                    campaign=campaign,
                    step=step,
                    contact=contact,
                    status=CampaignLog.LogStatus.SENT if success else CampaignLog.LogStatus.FAILED,
                    sent_at=timezone.now(),
                    error_message=error_msg
                )
        
        # Mark campaign as complete after processing all contacts and steps
        campaign.status = Campaign.CampaignStatus.COMPLETED
        campaign.save()

    @action(detail=True, methods=['post'], url_path='pause')
    def pause_campaign(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = Campaign.CampaignStatus.PAUSED
        campaign.save()
        # TODO: Add logic to cancel Celery tasks
        return Response({'status': 'Campaign has been paused.'})


class CampaignLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CampaignLog.objects.all().order_by('-sent_at')
    serializer_class = CampaignLogSerializer
    filterset_fields = ['campaign', 'contact', 'status', 'step']