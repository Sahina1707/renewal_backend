# File: apps/campaign_manager/helpers.py

from django.core.mail import send_mail
from django.conf import settings

def send_smtp_email(subject, body_html, to_email):
    """
    Sends an email using Django's email backend.
    This respects the EMAIL_BACKEND setting in settings.py.
    """
    try:
        send_mail(
            subject=subject,
            message='',  # Plain text message (optional)
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[to_email],
            html_message=body_html,
            fail_silently=False,
        )
        print(f"Successfully sent email to {to_email}")
        return True, None  # (success, error_message)

    except Exception as e:
        print(f"Error: Failed to send email to {to_email}. Error: {e}")
        return False, str(e)  # (success, error_message)