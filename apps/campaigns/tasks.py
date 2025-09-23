"""
Celery tasks for campaign management
"""

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_pending_campaigns():
    """
    Process scheduled campaigns that are ready to be sent.
    This task runs every 5 minutes via Celery Beat.
    """
    try:
        from apps.campaigns.models import Campaign
        from apps.campaigns.services import EmailCampaignService
        
        current_time = timezone.now()
        logger.info(f"Processing pending campaigns at {current_time}")
        
        # Find campaigns that are scheduled and ready to be sent
        scheduled_campaigns = Campaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=current_time,
            is_deleted=False
        ).select_related('template', 'communication_provider')
        
        logger.info(f"Found {scheduled_campaigns.count()} scheduled campaigns ready to send")
        
        processed_count = 0
        for campaign in scheduled_campaigns:
            try:
                logger.info(f"Processing scheduled campaign: {campaign.name} (ID: {campaign.id})")
                
                # Update campaign status to running
                campaign.status = 'running'
                campaign.started_at = current_time
                campaign.save()
                
                # Send emails for this campaign
                result = EmailCampaignService.send_campaign_emails(campaign.id)
                
                if result.get('success', False):
                    logger.info(f"Successfully processed campaign {campaign.id}: {result.get('message', '')}")
                    processed_count += 1
                else:
                    logger.error(f"Failed to process campaign {campaign.id}: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error processing campaign {campaign.id}: {str(e)}")
                # Mark campaign as failed
                campaign.status = 'cancelled'
                campaign.save()
                continue
        
        logger.info(f"Processed {processed_count} scheduled campaigns successfully")
        return f"Processed {processed_count} scheduled campaigns"
        
    except Exception as e:
        logger.error(f"Error in process_pending_campaigns task: {str(e)}")
        raise


@shared_task
def update_campaign_metrics():
    """
    Update campaign metrics and statistics.
    This task runs every 15 minutes via Celery Beat.
    """
    try:
        from apps.campaigns.models import Campaign, CampaignRecipient
        
        logger.info("Updating campaign metrics")
        
        # Update campaign statistics
        campaigns = Campaign.objects.filter(
            status__in=['running', 'completed'],
            is_deleted=False
        )
        
        updated_count = 0
        for campaign in campaigns:
            try:
                campaign.update_campaign_statistics()
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating metrics for campaign {campaign.id}: {str(e)}")
                continue
        
        logger.info(f"Updated metrics for {updated_count} campaigns")
        return f"Updated metrics for {updated_count} campaigns"
        
    except Exception as e:
        logger.error(f"Error in update_campaign_metrics task: {str(e)}")
        raise


@shared_task
def send_scheduled_campaign_email(campaign_id):
    """
    Send emails for a specific scheduled campaign.
    This can be used for individual campaign scheduling.
    """
    try:
        from apps.campaigns.models import Campaign
        from apps.campaigns.services import EmailCampaignService
        
        logger.info(f"Sending scheduled campaign email for campaign {campaign_id}")
        
        campaign = Campaign.objects.get(id=campaign_id)
        
        # Check if campaign is still scheduled and ready
        if campaign.status != 'scheduled':
            logger.warning(f"Campaign {campaign_id} is not in scheduled status: {campaign.status}")
            return f"Campaign {campaign_id} is not scheduled"
        
        # Update status to running
        campaign.status = 'running'
        campaign.started_at = timezone.now()
        campaign.save()
        
        # Send emails
        result = EmailCampaignService.send_campaign_emails(campaign_id)
        
        if result.get('success', False):
            logger.info(f"Successfully sent scheduled campaign {campaign_id}")
            return f"Successfully sent campaign {campaign_id}"
        else:
            logger.error(f"Failed to send scheduled campaign {campaign_id}: {result.get('error', 'Unknown error')}")
            return f"Failed to send campaign {campaign_id}"
            
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return f"Campaign {campaign_id} not found"
    except Exception as e:
        logger.error(f"Error sending scheduled campaign {campaign_id}: {str(e)}")
        raise


@shared_task
def cleanup_old_campaigns():
    """
    Clean up old completed campaigns and their data.
    This task runs weekly via Celery Beat.
    """
    try:
        from apps.campaigns.models import Campaign, CampaignRecipient
        from datetime import timedelta
        
        # Clean up campaigns older than 1 year
        cutoff_date = timezone.now() - timedelta(days=365)
        
        old_campaigns = Campaign.objects.filter(
            status='completed',
            completed_at__lt=cutoff_date,
            is_deleted=False
        )
        
        cleaned_count = 0
        for campaign in old_campaigns:
            try:
                # Soft delete the campaign
                campaign.is_deleted = True
                campaign.deleted_at = timezone.now()
                campaign.save()
                
                # Clean up old recipients
                CampaignRecipient.objects.filter(
                    campaign=campaign,
                    created_at__lt=cutoff_date
                ).update(is_deleted=True, deleted_at=timezone.now())
                
                cleaned_count += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up campaign {campaign.id}: {str(e)}")
                continue
        
        logger.info(f"Cleaned up {cleaned_count} old campaigns")
        return f"Cleaned up {cleaned_count} old campaigns"
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_campaigns task: {str(e)}")
        raise
