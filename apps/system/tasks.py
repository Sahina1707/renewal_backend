from celery import shared_task
from django.utils import timezone
from .models import SystemSettings
from .services import BackupService
import logging

logger = logging.getLogger(__name__)

@shared_task
def perform_system_backup():
    """
    Periodic task to perform system backup if enabled.
    """
    try:
        settings = SystemSettings.get_settings()
        
        if not settings.auto_backup:
            logger.info("Auto backup is disabled. Skipping.")
            return "Skipped (Disabled)"
            
        logger.info("Starting scheduled system backup...")
        s3_url = BackupService.create_backup()
        
        if s3_url:
            msg = f"Backup completed successfully. URL: {s3_url}"
            logger.info(msg)
            return msg
        else:
            msg = "Backup failed. Check logs for details."
            logger.error(msg)
            return msg
            
    except Exception as e:
        logger.exception(f"Error in perform_system_backup task: {str(e)}")
        return f"Error: {str(e)}"
