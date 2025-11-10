import logging
from typing import List, Dict, Any
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from .models import EmailManager

logger = logging.getLogger(__name__)


class EmailManagerService:
    
    @staticmethod
    def parse_email_list(email_string: str) -> List[str]:
        if not email_string:
            return []
        emails = [email.strip() for email in email_string.split(',') if email.strip()]
        return emails
    
    @staticmethod
    def send_email(email_manager: EmailManager) -> Dict[str, Any]:
        
        try:
            if email_manager.schedule_send and email_manager.schedule_date_time:
                if timezone.now() < email_manager.schedule_date_time:
                    EmailManager.objects.filter(id=email_manager.id).update(
                        email_status='scheduled'
                    )
                    email_manager.refresh_from_db()
                    schedule_dt = email_manager.schedule_date_time
                    scheduled_at_str = schedule_dt.isoformat() if schedule_dt else None
                    return {
                        'success': True,
                        'message': 'Email scheduled for sending',
                        'scheduled_at': scheduled_at_str
                    }
            
            to_emails = [str(email_manager.to)]
            cc_email_str = str(email_manager.cc) if email_manager.cc else ''
            bcc_email_str = str(email_manager.bcc) if email_manager.bcc else ''
            cc_emails = EmailManagerService.parse_email_list(cc_email_str)
            bcc_emails = EmailManagerService.parse_email_list(bcc_email_str)
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
            
            msg = EmailMultiAlternatives(
                subject=str(email_manager.subject),
                body=str(email_manager.message), 
                from_email=from_email,
                to=to_emails,
                cc=cc_emails if cc_emails else None,
                bcc=bcc_emails if bcc_emails else None
            )
            
            msg.send(fail_silently=False)
            
            now = timezone.now()
            EmailManager.objects.filter(id=email_manager.id).update(
                email_status='sent',
                sent_at=now,
                error_message=None
            )
            email_manager.refresh_from_db()
            
            logger.info(f"Email sent successfully to {email_manager.to} - Subject: {email_manager.subject}")
            
            sent_at_value = email_manager.sent_at
            sent_at_str = sent_at_value.isoformat() if sent_at_value else None
            
            return {
                'success': True,
                'message': 'Email sent successfully',
                'sent_at': sent_at_str
            }
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Failed to send email to {email_manager.to}: {error_message}")
            
            EmailManager.objects.filter(id=email_manager.id).update(
                email_status='failed',
                error_message=error_message
            )
            email_manager.refresh_from_db()
            
            return {
                'success': False,
                'message': f'Failed to send email: {error_message}',
                'error': error_message
            }
    
    @staticmethod
    def send_scheduled_emails() -> Dict[str, Any]:
        
        try:
            now = timezone.now()
            scheduled_emails = EmailManager.objects.filter(
                schedule_send=True,
                schedule_date_time__lte=now,
                email_status__in=['pending', 'scheduled'],
                is_deleted=False
            )
            
            sent_count = 0
            failed_count = 0
            
            for email in scheduled_emails:
                result = EmailManagerService.send_email(email)
                if result['success']:
                    sent_count += 1
                else:
                    failed_count += 1
            
            return {
                'success': True,
                'message': f'Processed {scheduled_emails.count()} scheduled emails',
                'sent': sent_count,
                'failed': failed_count
            }
            
        except Exception as e:
            logger.error(f"Error processing scheduled emails: {str(e)}")
            return {
                'success': False,
                'message': f'Error processing scheduled emails: {str(e)}',
                'error': str(e)
            }

