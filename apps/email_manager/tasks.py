from celery import shared_task
from .services import EmailManagerService, EmailInboxService

@shared_task
def process_scheduled_emails():
    """
    Send emails that are scheduled and due for sending.
    """
    EmailManagerService.send_scheduled_emails()

@shared_task
def fetch_and_process_incoming_emails():
    """
    Fetch new incoming replies and store them in email_manager_inbox table.
    """
    EmailInboxService.fetch_incoming_emails()
