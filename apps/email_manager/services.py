import logging
import smtplib
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
from django.db.models import Q
from email.utils import make_msgid
from django.core.mail import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
                    # Do NOT return here — just skip sending
                    return {'success': False, 'message': 'Not time yet'}

\
            subject = str(email_manager.subject)
            message = str(email_manager.message)

            if email_manager.policy_number:
                try:
                    policy = Policy.objects.get(policy_number=email_manager.policy_number)
                    customer = policy.customer

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
                    logger.warning(f"Policy {email_manager.policy_number} not found. Sending static email.")
                except Exception as e:
                    logger.error(f"Error rendering email for {email_manager.id}: {e}")

            # Email fields
            to_emails = [str(email_manager.to)]
            cc_emails = EmailManagerService.parse_email_list(str(email_manager.cc or ''))
            bcc_emails = EmailManagerService.parse_email_list(str(email_manager.bcc or ''))
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')

            custom_msg_id = make_msgid(domain="nbinteli1001.welleazy.com")
            msg = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email,
                to=to_emails,
                cc=cc_emails if cc_emails else None,
                bcc=bcc_emails if bcc_emails else None,
                headers={'Message-ID': custom_msg_id}  
            )

            # Send email
            msg.send(fail_silently=False)

            real_msg_id = custom_msg_id.strip("<>").lower()

            # Update status in DB
            now = timezone.now()
            EmailManager.objects.filter(id=email_manager.id).update(
                message_id=real_msg_id,
                email_status='sent',
                sent_at=now,
                error_message=None
            )

            email_manager.refresh_from_db()

            logger.info(f"✅ Email sent successfully to {email_manager.to} | Message-ID: {real_msg_id}")

            sent_at_value = email_manager.sent_at
            sent_at_str = sent_at_value.isoformat() if sent_at_value else None

            return {
                'success': True,
                'message': 'Email sent successfully',
                'sent_at': sent_at_str,
                'message_id': real_msg_id
            }

        except Exception as e:
            error_message = str(e)
            logger.error(f"❌ Failed to send email to {email_manager.to}: {error_message}")

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
                is_deleted=False
            ).filter(
                Q(email_status="pending") | Q(email_status="scheduled")
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
        
    @staticmethod
    def send_reply_email(reply_obj):
        from email.utils import make_msgid
        from django.utils import timezone

        new_msg_id = make_msgid(domain="nbinteli1001.welleazy.com")

        email = EmailMessage(
            subject=reply_obj.subject,
            body=reply_obj.message,
            from_email=reply_obj.from_email,
            to=[reply_obj.to_email],
            headers={
                "Message-ID": new_msg_id,
                "In-Reply-To": reply_obj.in_reply_to,
                "References": reply_obj.in_reply_to,
            }
        )

        email.send()

        reply_obj.message_id = new_msg_id.strip("<>")
        reply_obj.sent_at = timezone.now()
        reply_obj.status = "sent"
        reply_obj.save()

        return True
    
    @staticmethod
    def send_reply_smtp(to_email, subject, message, html_message=None):
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.DEFAULT_FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        part1 = MIMEText(message, "plain")
        msg.attach(part1)

        if html_message:
            part2 = MIMEText(html_message, "html")
            msg.attach(part2)

        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.sendmail(settings.DEFAULT_FROM_EMAIL, to_email, msg.as_string())

        return True

    
class EmailInboxService:

    @staticmethod
    def clean_text(text):
        return text.strip() if text else ""
    
    @staticmethod
    def clean_message_id(raw_id):
        if not raw_id:
            return None
        try:
            cleaned = raw_id.strip().replace('<', '').replace('>', '').replace('\r', '').replace('\n', '').strip()
            return cleaned
        except Exception as e:
            logger.error(f"Error cleaning Message-ID: {e}")
            return None


    @staticmethod
    def fetch_incoming_emails():
        IMAP_HOST = getattr(settings, "IMAP_HOST", "imap.gmail.com")
        IMAP_USER = getattr(settings, "EMAIL_HOST_USER")
        IMAP_PASS = getattr(settings, "EMAIL_HOST_PASSWORD")
        IMAP_PORT = int(getattr(settings, "IMAP_PORT", 993))

        if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
            logger.error("❌ IMAP credentials not configured in settings.")
            return {"success": False, "message": "IMAP credentials missing"}

        try:
            logger.info(f"📥 Connecting to IMAP: {IMAP_HOST}:{IMAP_PORT} as {IMAP_USER}")
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASS)
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            if status != "OK":
                mail.logout()
                return {"success": False, "message": "Failed to search inbox"}

            email_ids = messages[0].split()
            processed = 0
            skipped = 0
            linked = 0

            for eid in email_ids[-50:]: 
                try:
                    status, msg_data = mail.fetch(eid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    msg_id = msg.get("Message-ID")
                    if not msg_id:
                        logger.debug("⏩ Skipped: No Message-ID header present.")
                        skipped += 1
                        continue

                    msg_id_clean = EmailInboxService.clean_message_id(msg_id)

                    if EmailManagerInbox.objects.filter(message_id__iexact=msg_id_clean).exists():
                        skipped += 1
                        continue

                    from_ = msg.get("From", "")
                    to_ = msg.get("To", "")
                    subject_raw = msg.get("Subject", "")
                    in_reply_to_raw = msg.get("In-Reply-To")
                    references_raw = msg.get("References")

                    subject_parts = decode_header(subject_raw)
                    subject = ""
                    for part, encoding in subject_parts:
                        if isinstance(part, bytes):
                            subject += part.decode(encoding or "utf-8", errors="ignore")
                        else:
                            subject += part
                    subject = EmailInboxService.clean_text(subject)

                    in_reply_to = EmailInboxService.clean_message_id(in_reply_to_raw)
                    references = [
                        EmailInboxService.clean_message_id(ref)
                        for ref in references_raw.split()
                        if ref.strip()
                    ] if references_raw else []

                    candidate_ids = []
                    if in_reply_to:
                        candidate_ids.append(in_reply_to)
                    candidate_ids.extend(references)

                    logger.debug(f"📨 Processing email '{subject}' | Candidates: {candidate_ids}")

                    related_email = None
                    for mid in candidate_ids:
                        if not mid:
                            continue
                        normalized_mid = mid.lower().strip().replace("<", "").replace(">", "")
                        try:
                            related_email = EmailManager.objects.filter(
                                message_id__iexact=normalized_mid,
                                is_deleted=False
                            ).first()

                            if not related_email:
                                related_email = EmailManager.objects.filter(
                                    message_id__icontains=normalized_mid,
                                    is_deleted=False
                                ).first()

                            if not related_email:
                                related_email = EmailManager.objects.filter(
                                    message_id__icontains=mid.lower(),
                                    is_deleted=False
                                ).first()

                            if related_email:
                                logger.info(
                                    f"✅ Linked reply to EmailManager ID={related_email.id}, "
                                    f"policy={related_email.policy_number}, subject={subject}"
                                )
                                linked += 1
                                break
                        except Exception as ex:
                            logger.exception(f"⚠️ Error linking MID {mid}: {ex}")
                            continue

                    body = ""
                    html_body = ""
                    attachments = []

                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition", ""))

                            if "attachment" in content_disposition:
                                filename = part.get_filename()
                                if filename:
                                    try:
                                        decoded = decode_header(filename)[0]
                                        filename = (
                                            decoded[0]
                                            if isinstance(decoded[0], str)
                                            else decoded[0].decode(decoded[1] or "utf-8")
                                        )
                                    except Exception:
                                        filename = filename or "unknown"
                                    payload = part.get_payload(decode=True)
                                    attachments.append({
                                        "filename": filename,
                                        "size": len(payload) if payload else 0,
                                        "content_type": content_type,
                                    })
                                continue

                            payload = part.get_payload(decode=True)
                            if not payload:
                                continue
                            text = payload.decode(errors="ignore")

                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                body += text + "\n"
                            elif content_type == "text/html" and "attachment" not in content_disposition:
                                html_body += text
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode(errors="ignore")

                    if related_email:
                        EmailManagerInbox.objects.create(
                            from_email=from_,
                            to_email=to_,
                            subject=subject,
                            message=EmailInboxService.clean_text(body),
                            html_message=html_body.strip() or None,
                            received_at=timezone.now(),
                            message_id=msg_id_clean,
                            in_reply_to=in_reply_to or (references[0] if references else None),
                            references=references_raw,
                            attachments=attachments if attachments else None,
                            related_email=related_email,
                            is_read=False,
                        )
                        processed += 1
                        logger.info(
                            f"📩 Stored reply from {from_} for policy {related_email.policy_number} | Subject: {subject}"
                        )
                    else:
                        skipped += 1
                        logger.debug(f"⏩ Skipped unrelated email: {subject} from {from_}")

                except Exception as e:
                    logger.error(f"Error processing email ID {eid}: {str(e)}", exc_info=True)
                    continue

            mail.logout()
            logger.info(f"📬 Summary: Processed={processed}, Skipped={skipped}, Linked={linked}")

            return {
                "success": True,
                "message": "Emails synced successfully",
                "processed": processed,
                "skipped": skipped,
                "linked_replies": linked,
            }

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
            return {"success": False, "message": f"IMAP error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in fetch_incoming_emails: {e}", exc_info=True)
            return {"success": False, "message": f"Sync failed: {str(e)}"}