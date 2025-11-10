from celery import shared_task
from apps.email_manager.services import EmailManagerService

@shared_task
def process_scheduled_emails():
    """
    This Celery task sends all emails that are due for scheduled delivery.
    """
    EmailManagerService.send_scheduled_emails()
