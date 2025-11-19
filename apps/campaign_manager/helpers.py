# File: apps/campaign_manager/helpers.py

from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_smtp_email(subject, body_html, to_email):
    """
    Sends an email using standard SMTP.
    WARNING: This CANNOT get a message_id, so tracking will not work.
    """
    try:
        send_mail(
            subject=subject,
            message='', # Use html_message instead
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=body_html,
            fail_silently=False,
        )
        
        message_id = None 

        logger.info(f"Successfully sent email to {to_email} via SMTP.")
        return True, None, message_id 

    except Exception as e:
        logger.error(f"Error: Failed to send SMTP email to {to_email}. Exception: {e}", exc_info=True)
        return False, str(e), None  