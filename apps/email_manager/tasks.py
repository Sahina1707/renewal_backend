from celery import shared_task
from .services import EmailManagerService, EmailInboxService

@shared_task
def process_scheduled_emails():
    EmailManagerService.send_scheduled_emails()

@shared_task
def fetch_and_process_incoming_emails():
    EmailInboxService.fetch_incoming_emails()
