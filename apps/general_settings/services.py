import logging
from .models import UserSettings
from django.db.models import Q
from apps.email_provider.services import EmailProviderService
from apps.sms_provider.services import SmsService

logger = logging.getLogger(__name__)

def send_user_notification(user, notification_type, message, subject=None):
    try:
        settings = UserSettings.objects.get(user=user)
    except UserSettings.DoesNotExist:
        logger.warning(f"No UserSettings found for user {user.id}. Skipping notification.")
        return

    # Try to find associated customer for billing/logging
    customer = None
    try:
        from apps.customers.models import Customer
        customer = Customer.objects.filter(
            Q(user=user) | Q(email=user.email)
        ).first()
    except Exception:
        pass

    if settings.email_notifications and user.email:
        try:
            email_service = EmailProviderService()
            # Use a default subject if none provided
            final_subject = subject or f"Notification: {notification_type.replace('_', ' ').title()}"
            
            email_service.send_email(
                to_emails=[user.email],
                subject=final_subject,
                text_content=message,
                html_content=f"<p>{message}</p>",
                customer=customer
            )
            logger.info(f"[EMAIL SENT] To: {user.email} | Type: {notification_type}")
        except Exception as e:
            logger.error(f"[EMAIL FAILED] To: {user.email} | Error: {str(e)}")
    else:
        logger.info(f"[EMAIL SKIPPED] User {user.username} disabled emails or has no email address.")
    if settings.sms_notifications:
        phone = getattr(user, 'phone_number', None) 
        
        if not phone and hasattr(user, 'profile'):
             phone = getattr(user.profile, 'phone_number', None)

        if phone:
            try:
                sms_service = SmsService().get_service_instance() 
                sms_service.send_sms(to_phone=phone, message=message, customer=customer)
                logger.info(f"[SMS SENT] To: {phone} | Type: {notification_type}")
            except Exception as e:
                logger.error(f"[SMS FAILED] To: {phone} | Error: {str(e)}")
        else:
            logger.warning(f"[SMS SKIPPED] User {user.username} enabled SMS but has no phone number.")
    else:
        logger.info(f"[SMS SKIPPED] User {user.username} has disabled SMS notifications.")