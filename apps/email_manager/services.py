import logging
from typing import List, Dict, Any
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from .models import EmailManager
from django.template import Template as DjangoTemplate, Context
from apps.policies.models import Policy
from .models import EmailManagerInbox
import imaplib, email
from email.header import decode_header
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
            
            subject = str(email_manager.subject)
            message = str(email_manager.message)

            if email_manager.policy_number:
                try:
                    policy = Policy.objects.get(policy_number=email_manager.policy_number)
                    customer = policy.customer
                    
                    # Prepare context for template rendering
                    context = {
                        'first_name': customer.first_name,
                        'last_name': customer.last_name,
                        'policy_number': policy.policy_number,
                        'expiry_date': policy.end_date.strftime('%d-%m-%Y') if getattr(policy, 'end_date', None) else 'N/A',
                        'premium_amount': str(policy.premium_amount),
                        'customer_name': customer.full_name,
                        'renewal_date': policy.renewal_date.strftime('%Y-%m-%d') if policy.renewal_date else '',
                    }
                    
                    subject_template = DjangoTemplate(subject)
                    message_template = DjangoTemplate(message)

                    subject = subject_template.render(Context(context))
                    message = message_template.render(Context(context))

                except Policy.DoesNotExist:
                    logger.warning(f"Policy with number {email_manager.policy_number} not found. Sending email with static data.")
                except Exception as e:
                    logger.error(f"Error fetching policy or customer data for email {email_manager.id}: {e}")


            to_emails = [str(email_manager.to)]
            cc_email_str = str(email_manager.cc) if email_manager.cc else ''
            bcc_email_str = str(email_manager.bcc) if email_manager.bcc else ''
            cc_emails = EmailManagerService.parse_email_list(cc_email_str)
            bcc_emails = EmailManagerService.parse_email_list(bcc_email_str)
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=message, 
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

class EmailInboxService:

    @staticmethod
    def clean_text(text):
        return re.sub(r'\s+', ' ', text.strip()) if text else ""

    @staticmethod
    def fetch_incoming_emails():
        EMAIL_HOST = "imap.gmail.com"
        EMAIL_USER = "sahinayasin17@gmail.com"
        EMAIL_PASS = "dfdr ihth gmbs ntxk"

        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        _, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()

        for eid in email_ids[-50:]:  # fetch last 50
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or "utf-8", errors="ignore")

            from_ = msg.get("From")
            to_ = msg.get("To")
            msg_id = msg.get("Message-ID")
            in_reply_to = msg.get("In-Reply-To")

            # Skip if already exists
            if EmailManagerInbox.objects.filter(message_id=msg_id).exists():
                continue

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode(errors="ignore")
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            EmailManagerInbox.objects.create(
                from_email=from_,
                to_email=to_,
                subject=EmailInboxService.clean_text(subject),
                body=EmailInboxService.clean_text(body),
                message_id=msg_id,
                in_reply_to=in_reply_to,
                received_at=timezone.now(),
            )

        mail.logout()
        return {"success": True, "message": "Emails synced successfully."}
