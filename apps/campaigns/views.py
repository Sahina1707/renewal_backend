import logging
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.utils import timezone
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from .models import Campaign, CampaignRecipient, CampaignType
from .serializers import (
    CampaignSerializer, CampaignCreateSerializer
)
# FIXED: Removed send_campaign_emails_async from imports
from .services import EmailCampaignService 
from apps.core.pagination import StandardResultsSetPagination
from apps.files_upload.models import FileUpload
from apps.templates.models import Template
import base64
import urllib.parse

logger = logging.getLogger(__name__)

class CampaignViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Campaigns"""
    queryset = Campaign.objects.select_related('campaign_type', 'created_by', 'assigned_to')
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'campaign_type', 'created_by']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'status']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'])
    def test_action(self, request):
        """Test action to verify ViewSet actions work"""
        return Response({"message": "Test action works!", "status": "success"})

    @action(detail=False, methods=['post'], url_path='create-from-file')
    def create_from_file(self, request):
        """
        Create a campaign based on uploaded policy file with target audience filtering
        """
        try:
            serializer = CampaignCreateSerializer(data=request.data, context={'request': request})

            if serializer.is_valid():
                try:
                    campaign = serializer.save()

                    send_immediately = request.data.get('send_immediately', False)

                    response_data = {
                        "message": "Campaign created successfully",
                        "campaign": {
                            "id": campaign.id,
                            "name": campaign.name,
                            "campaign_type": campaign.campaign_type.name,
                            "template": campaign.template.name,
                            "status": campaign.status,
                            "target_count": campaign.target_count,
                            "created_at": campaign.created_at.isoformat(),
                            "channels": campaign.channels
                        },
                        "email_sending": {
                            "send_immediately": send_immediately,
                            "status": "completed" if campaign.status == 'completed' else "started" if send_immediately else "not_started",
                            "message": f"Emails sent to {campaign.target_count} recipients" if campaign.status == 'completed' else f"Emails are being sent to {campaign.target_count} recipients" if send_immediately else "Use send_emails endpoint to send emails"
                        }
                    }

                    return Response(response_data, status=status.HTTP_201_CREATED)

                except Exception as e:
                    logger.error(f"Error creating campaign: {str(e)}")
                    return Response(
                        {"error": f"Failed to create campaign: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                return Response(
                    {"error": "Validation failed", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Unexpected error in create_from_file: {str(e)}")
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def simple_test(self, request):
        """Simple test endpoint"""
        return Response({"message": "Simple test works!", "status": "success"})

    @action(detail=False, methods=['get'])
    def get_file_uploads(self, request):
        """Get available file uploads for campaign creation"""
        try:
            file_uploads = FileUpload.objects.filter(
                upload_status='completed'
            ).values('id', 'original_filename', 'successful_records', 'created_at')
            
            return Response({
                "file_uploads": list(file_uploads)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch file uploads: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def get_campaign_types(self, request):
        """Get available campaign types"""
        try:
            campaign_types = CampaignType.objects.all().values('id', 'name', 'description')
            
            return Response({
                "campaign_types": list(campaign_types)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch campaign types: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def get_email_templates(self, request):
        """Get available email templates"""
        try:
            templates = Template.objects.filter(
                template_type='email'
            ).values('id', 'name', 'subject')
            
            return Response({
                "templates": list(templates)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch email templates: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def get_campaign_metrics(self, request, pk=None):
        """Get detailed campaign metrics and engagement statistics"""
        try:
            campaign = self.get_object()

            campaign.update_campaign_statistics()

            metrics = campaign.get_campaign_metrics()

            recipients = campaign.recipients.all()
            recipient_breakdown = {
                'total_recipients': recipients.count(),
                'email_status': {
                    'pending': recipients.filter(email_status='pending').count(),
                    'sent': recipients.filter(email_status='sent').count(),
                    'delivered': recipients.filter(email_status='delivered').count(),
                    'failed': recipients.filter(email_status='failed').count(),
                    'bounced': recipients.filter(email_status='bounced').count(),
                },
                'engagement_status': {
                    'not_opened': recipients.filter(email_engagement='not_opened').count(),
                    'opened': recipients.filter(email_engagement='opened').count(),
                    'clicked': recipients.filter(email_engagement='clicked').count(),
                    'replied': recipients.filter(email_engagement='replied').count(),
                }
            }

            return Response({
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "status": campaign.status,
                "metrics": metrics,
                "recipient_breakdown": recipient_breakdown,
                "last_updated": timezone.now().isoformat()
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting campaign metrics: {str(e)}")
            return Response(
                {"error": f"Failed to get campaign metrics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def update_statistics(self, request, pk=None):
        """Manually update campaign statistics"""
        try:
            campaign = self.get_object()

            recipients = campaign.recipients.all()
            pending_count = recipients.filter(email_status='pending').count()
            sent_count = recipients.filter(email_status__in=['sent', 'delivered']).count()
            delivered_count = recipients.filter(email_status='delivered').count()
            failed_count = recipients.filter(email_status='failed').count()

            campaign.update_campaign_statistics()

            return Response({
                "message": "Campaign statistics updated successfully",
                "debug_info": {
                    "total_recipients": recipients.count(),
                    "pending_recipients": pending_count,
                    "sent_recipients": sent_count,
                    "delivered_recipients": delivered_count,
                    "failed_recipients": failed_count,
                },
                "campaign_stats": {
                    "sent_count": campaign.sent_count,
                    "delivered_count": campaign.delivered_count,
                    "opened_count": campaign.opened_count,
                    "clicked_count": campaign.clicked_count,
                    "target_count": campaign.target_count,
                },
                "updated_at": timezone.now().isoformat()
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error updating campaign statistics: {str(e)}")
            return Response(
                {"error": f"Failed to update statistics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def recipient_status(self, request, pk=None):
        """Get detailed recipient status for debugging"""
        try:
            campaign = self.get_object()
            recipients = campaign.recipients.all()

            status_breakdown = {}
            for status_choice in CampaignRecipient.DELIVERY_STATUS_CHOICES:
                status_code = status_choice[0]
                count = recipients.filter(email_status=status_code).count()
                if count > 0:
                    status_breakdown[status_code] = count

            sample_recipients = {}
            for status_code in status_breakdown.keys():
                sample = recipients.filter(email_status=status_code)[:3]
                sample_recipients[status_code] = [
                    {
                        'id': r.id,
                        'customer_email': r.customer.email,
                        'email_status': r.email_status,
                        'email_sent_at': r.email_sent_at.isoformat() if r.email_sent_at else None,
                        'email_delivered_at': r.email_delivered_at.isoformat() if r.email_delivered_at else None,
                        'created_at': r.created_at.isoformat()
                    }
                    for r in sample
                ]

            return Response({
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "total_recipients": recipients.count(),
                "status_breakdown": status_breakdown,
                "sample_recipients": sample_recipients,
                "current_campaign_counts": {
                    "sent_count": campaign.sent_count,
                    "delivered_count": campaign.delivered_count,
                    "opened_count": campaign.opened_count,
                    "clicked_count": campaign.clicked_count,
                    "target_count": campaign.target_count,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting recipient status: {str(e)}")
            return Response(
                {"error": f"Failed to get recipient status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def force_update_counts(self, request, pk=None):
        """Force update campaign counts - SIMPLE METHOD"""
        try:
            campaign = self.get_object()

            recipients = campaign.recipients.all()

            total_recipients = recipients.count()
            sent_count = recipients.filter(email_status__in=['sent', 'delivered']).count()
            delivered_count = recipients.filter(email_status='delivered').count()
            opened_count = recipients.filter(email_engagement__in=['opened', 'clicked', 'replied', 'forwarded']).count()
            clicked_count = recipients.filter(email_engagement__in=['clicked', 'replied', 'forwarded']).count()

            campaign.target_count = total_recipients
            campaign.sent_count = sent_count
            campaign.delivered_count = delivered_count
            campaign.opened_count = opened_count
            campaign.clicked_count = clicked_count

            campaign.save()

            return Response({
                "message": "Campaign counts updated successfully",
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "before_update": "Check database for previous values",
                "after_update": {
                    "target_count": campaign.target_count,
                    "sent_count": campaign.sent_count,
                    "delivered_count": campaign.delivered_count,
                    "opened_count": campaign.opened_count,
                    "clicked_count": campaign.clicked_count,
                },
                "recipient_details": {
                    "total_recipients": total_recipients,
                    "sent_recipients": sent_count,
                    "delivered_recipients": delivered_count,
                    "opened_recipients": opened_count,
                    "clicked_recipients": clicked_count,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error force updating campaign counts: {str(e)}")
            return Response(
                {"error": f"Failed to force update counts: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def send_emails(self, request, pk=None):
        """Send campaign emails"""
        try:
            campaign = self.get_object()

            if campaign.status not in ['draft', 'scheduled', 'running']: # Allowing running for testing
                return Response(
                    {"error": "Campaign emails can only be sent for draft, scheduled or running campaigns"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            result = EmailCampaignService.send_campaign_emails(campaign.id)

            if "error" in result:
                return Response(
                    {"error": result["error"]},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error sending campaign emails: {str(e)}")
            return Response(
                {"error": f"Failed to send emails: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def get_all_campaign_stats(self, request):
        """Get statistics for all campaigns"""
        try:
            campaigns = Campaign.objects.all().order_by('-created_at')

            campaign_stats = []
            for campaign in campaigns:
                campaign.update_campaign_statistics()

                stats = {
                    'id': campaign.id,
                    'name': campaign.name,
                    'status': campaign.status,
                    'created_at': campaign.created_at.isoformat(),
                    'target_count': campaign.target_count,
                    'sent_count': campaign.sent_count,
                    'delivered_count': campaign.delivered_count,
                    'opened_count': campaign.opened_count,
                    'clicked_count': campaign.clicked_count,
                    'total_responses': campaign.total_responses,
                }

                if campaign.sent_count > 0:
                    stats['delivery_rate'] = round((campaign.delivered_count / campaign.sent_count) * 100, 2)
                else:
                    stats['delivery_rate'] = 0

                if campaign.delivered_count > 0:
                    stats['open_rate'] = round((campaign.opened_count / campaign.delivered_count) * 100, 2)
                else:
                    stats['open_rate'] = 0

                if campaign.opened_count > 0:
                    stats['click_rate'] = round((campaign.clicked_count / campaign.opened_count) * 100, 2)
                else:
                    stats['click_rate'] = 0

                campaign_stats.append(stats)

            return Response({
                "total_campaigns": len(campaign_stats),
                "campaigns": campaign_stats,
                "last_updated": timezone.now().isoformat()
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting campaign statistics: {str(e)}")
            return Response(
                {"error": f"Failed to get campaign statistics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, pk=None):
       
        try:
            campaign = self.get_object()
            new_simplified_status = request.data.get('status')
            
            if not new_simplified_status:
                return Response({
                    "success": False,
                    "message": "Status is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            valid_statuses = ['active', 'paused']
            if new_simplified_status not in valid_statuses:
                return Response({
                    "success": False,
                    "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            current_simplified_status = campaign.get_simplified_status()
            if current_simplified_status == new_simplified_status:
                return Response({
                    "success": True,
                    "message": f"Campaign is already {new_simplified_status}",
                    "data": {
                        "campaign_id": campaign.id,
                        "current_status": current_simplified_status,
                        "new_status": new_simplified_status,
                        "simplified_status": new_simplified_status
                    }
                }, status=status.HTTP_200_OK)
            
            campaign.set_simplified_status(new_simplified_status)
            
            if new_simplified_status == 'active' and current_simplified_status == 'paused':
                campaign.started_at = timezone.now()
                campaign.save(update_fields=['started_at'])
            elif new_simplified_status == 'paused' and current_simplified_status == 'active':
                pass
            
            return Response({
                "success": True,
                "message": f"Campaign status changed from {current_simplified_status} to {new_simplified_status}",
                "data": {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "previous_status": current_simplified_status,
                    "new_status": new_simplified_status,
                    "simplified_status": new_simplified_status,
                    "updated_at": campaign.updated_at.isoformat()
                }
            }, status=status.HTTP_200_OK)
            
        except Campaign.DoesNotExist:
            return Response({
                "success": False,
                "message": "Campaign not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error changing campaign status: {str(e)}")
            return Response({
                "success": False,
                "message": f"Error changing campaign status: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([])
@authentication_classes([])
def simulate_email_delivery(request):
    try:
        campaign_id = request.data.get('campaign_id')
        delivery_rate = request.data.get('delivery_rate', 0.9)  

        if not campaign_id:
            return Response(
                {"error": "campaign_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .models import Campaign, CampaignRecipient
        import random

        campaign = Campaign.objects.get(id=campaign_id)
        sent_recipients = campaign.recipients.filter(email_status='sent')

        delivered_count = 0
        bounced_count = 0

        for recipient in sent_recipients:
            if random.random() < delivery_rate:
                recipient.mark_delivered('email')
                delivered_count += 1
            else:
                recipient.email_status = 'bounced'
                recipient.save()
                bounced_count += 1

        campaign.update_campaign_statistics()

        return Response({
            "message": "Email delivery simulation completed",
            "campaign_id": campaign_id,
            "delivered_count": delivered_count,
            "bounced_count": bounced_count,
            "delivery_rate": f"{(delivered_count / (delivered_count + bounced_count) * 100):.1f}%" if (delivered_count + bounced_count) > 0 else "0%"
        }, status=status.HTTP_200_OK)

    except Campaign.DoesNotExist:
        return Response(
            {"error": "Campaign not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error simulating email delivery: {str(e)}")
        return Response(
            {"error": f"Failed to simulate delivery: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([])
@authentication_classes([])
def debug_campaign_data(request):
    try:
        campaign_id = request.GET.get('campaign_id')
        if not campaign_id:
            return Response({"error": "campaign_id required"}, status=400)

        from .models import Campaign, CampaignRecipient

        campaign = Campaign.objects.get(id=campaign_id)
        recipients = CampaignRecipient.objects.filter(campaign=campaign)

        debug_data = {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "sent_count": campaign.sent_count,
                "delivered_count": campaign.delivered_count,
                "opened_count": campaign.opened_count,
                "clicked_count": campaign.clicked_count,
            },
            "recipients": []
        }

        for recipient in recipients:
            debug_data["recipients"].append({
                "id": recipient.id,
                "customer_email": recipient.customer.email,
                "email_status": recipient.email_status,
                "email_engagement": recipient.email_engagement,
                "email_sent_at": recipient.email_sent_at.isoformat() if recipient.email_sent_at else None,
                "email_opened_at": recipient.email_opened_at.isoformat() if recipient.email_opened_at else None,
                "email_clicked_at": recipient.email_clicked_at.isoformat() if recipient.email_clicked_at else None,
            })

        return Response(debug_data)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_campaigns(request):
    try:
        campaigns = Campaign.objects.all().order_by('-created_at')

        campaigns_data = []
        for campaign in campaigns:
            original_filename = "N/A"
            if campaign.upload:
                original_filename = campaign.upload.original_filename

            campaign_data = {
                "id": campaign.id,
                "campaign_name": campaign.name,
                "created_date": campaign.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "target_count": campaign.target_count,
                "sent_count": campaign.sent_count,
                "opened_count": campaign.opened_count,
                "clicked_count": campaign.clicked_count,
                "delivered_count": campaign.delivered_count,
                "status": campaign.status,
                "original_filename": original_filename,
                "campaign_type": campaign.campaign_type.name if campaign.campaign_type else "N/A",
                "template_name": campaign.template.name if campaign.template else "N/A",
                "schedule_type": campaign.schedule_type,
                "scheduled_at": campaign.scheduled_at.strftime("%d/%m/%Y %H:%M:%S") if campaign.scheduled_at else None
            }
            campaigns_data.append(campaign_data)

        response_data = {
            "success": True,
            "message": f"Found {len(campaigns_data)} campaigns",
            "total_campaigns": len(campaigns_data),
            "campaigns": campaigns_data
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "message": f"Error fetching campaigns: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_campaign_status(request, campaign_id):
    """
    Update campaign status (active/paused only)
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        
        new_status = request.data.get('status')
        
        if not new_status:
            return Response({
                "success": False,
                "message": "status is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        valid_statuses = ['active', 'paused']
        if new_status.lower() not in valid_statuses:
            return Response({
                "success": False,
                "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        new_status = new_status.lower()
        
        campaign.status = new_status
        campaign.save(update_fields=['status'])
        
        return Response({
            "success": True,
            "message": f"Campaign status updated to {new_status}",
            "data": {
                "id": campaign.id,
                "campaign_name": campaign.name,
                "status": campaign.status
            }
        }, status=status.HTTP_200_OK)
        
    except Campaign.DoesNotExist:
        return Response({
            "success": False,
            "message": f"Campaign with ID {campaign_id} not found"
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({
            "success": False,
            "message": f"Error updating campaign status: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class EmailTrackingView(View):
    """Handle email tracking for opens and clicks"""

    def get(self, request):
        """Track email opens using tracking pixel"""
        pixel_data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
        response = HttpResponse(pixel_data, content_type='image/png')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        try:
            tracking_id = request.GET.get('t')
            if not tracking_id:
                logger.warning("No tracking ID provided")
                return response

            recipient = CampaignRecipient.objects.select_related('campaign', 'customer').get(tracking_id=tracking_id)

            logger.info(f"Email open tracked: {recipient.customer.email}, Campaign: {recipient.campaign.name}")

            if recipient.email_engagement == 'not_opened':
                recipient.email_engagement = 'opened'
                recipient.email_opened_at = timezone.now()
                if not recipient.email_delivered_at:
                    recipient.email_delivered_at = timezone.now()

                recipient.save()

                campaign = recipient.campaign
                campaign.update_campaign_statistics()

                logger.info(f"Email opened: Campaign {campaign.name}, Customer: {recipient.customer.email}")
                logger.info(f"Campaign stats updated - Sent: {campaign.sent_count}, Delivered: {campaign.delivered_count}, Opened: {campaign.opened_count}")

            return response

        except CampaignRecipient.DoesNotExist:
            logger.warning(f"Invalid tracking ID: {tracking_id}")
            return response
        except Exception as e:
            logger.error(f"Error tracking email open: {str(e)}")
            return response


@method_decorator(csrf_exempt, name='dispatch')
class EmailClickTrackingView(View):
    """Handle email click tracking"""

    def get(self, request):
        """Track email clicks and redirect to original URL"""
        try:
            tracking_id = request.GET.get('t')
            original_url = request.GET.get('url', 'http://localhost:8000')

            if not tracking_id:
                return HttpResponseRedirect(original_url)

            recipient = CampaignRecipient.objects.select_related('campaign', 'customer').get(tracking_id=tracking_id)

            logger.info(f"Email click tracked: {recipient.customer.email}, Campaign: {recipient.campaign.name}")

            if recipient.email_engagement in ['not_opened', 'opened']:
                recipient.email_engagement = 'clicked'
                recipient.email_clicked_at = timezone.now()

                if not recipient.email_delivered_at:
                    recipient.email_delivered_at = timezone.now()
                if not recipient.email_opened_at:
                    recipient.email_opened_at = timezone.now()

                recipient.save()

                campaign = recipient.campaign
                campaign.update_campaign_statistics()

                logger.info(f"Email clicked: Campaign {campaign.name}, Customer: {recipient.customer.email}")
                logger.info(f"Campaign stats updated - Sent: {campaign.sent_count}, Delivered: {campaign.delivered_count}, Opened: {campaign.opened_count}, Clicked: {campaign.clicked_count}")

            return HttpResponseRedirect(original_url)

        except CampaignRecipient.DoesNotExist:
            logger.warning(f"Invalid tracking ID for click: {tracking_id}")
            return HttpResponseRedirect('http://localhost:8000')
        except Exception as e:
            logger.error(f"Error tracking email click: {str(e)}")
            return HttpResponseRedirect('http://localhost:8000')


@api_view(['GET'])
@permission_classes([]) 
@authentication_classes([]) 
def test_tracking_pixel(request):
    """Test endpoint to verify tracking pixel functionality"""
    try:
        tracking_id = request.GET.get('t')
        if not tracking_id:
            return Response({
                "success": False,
                "message": "Missing tracking ID parameter 't'"
            }, status=status.HTTP_400_BAD_REQUEST)

        recipient = CampaignRecipient.objects.select_related('campaign').get(tracking_id=tracking_id)

        return Response({
            "success": True,
            "message": "Tracking ID found",
            "data": {
                "tracking_id": tracking_id,
                "campaign_id": recipient.campaign.id,
                "customer_email": recipient.customer.email,
                "tracking_url": f"http://localhost:8000/api/campaigns/track-open/?t={tracking_id}",
                "pixel_html": f'<img src="http://localhost:8000/api/campaigns/track-open/?t={tracking_id}" width="1" height="1" style="display:none;" alt="" />'
            }
        }, status=status.HTTP_200_OK)

    except CampaignRecipient.DoesNotExist:
        return Response({
            "success": False,
            "message": f"No recipient found with tracking ID: {tracking_id}"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            "success": False,
            "message": f"Error: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_campaign_tracking_stats(request, campaign_id):
    """Get tracking statistics for a specific campaign"""
    try:
        campaign = Campaign.objects.get(id=campaign_id)

        recipients = CampaignRecipient.objects.filter(campaign=campaign)

        total_recipients = recipients.count()
        open_rate = (campaign.opened_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0
        click_rate = (campaign.clicked_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0
        delivery_rate = (campaign.delivered_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0

        return Response({
            "success": True,
            "data": {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "tracking_stats": {
                    "total_recipients": total_recipients,
                    "sent_count": campaign.sent_count,
                    "delivered_count": campaign.delivered_count,
                    "opened_count": campaign.opened_count,
                    "clicked_count": campaign.clicked_count,
                    "delivery_rate": round(delivery_rate, 2),
                    "open_rate": round(open_rate, 2),
                    "click_rate": round(click_rate, 2)
                },
                "sample_tracking_urls": [
                    {
                        "recipient_email": recipient.customer.email,
                        "tracking_id": recipient.tracking_id,
                        "open_tracking_url": f"http://localhost:8000/api/campaigns/track-open/?t={recipient.tracking_id}",
                        "click_tracking_url": f"http://localhost:8000/api/campaigns/track-click/?t={recipient.tracking_id}&url=https://example.com"
                    }
                    for recipient in recipients[:3]  
                ]
            }
        }, status=status.HTTP_200_OK)

    except Campaign.DoesNotExist:
        return Response({
            "success": False,
            "message": f"Campaign with ID {campaign_id} not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            "success": False,
            "message": f"Error: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)