import email
import imaplib
import logging
import os
from email.header import decode_header
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from celery import shared_task

from .services import EmailInboxService

logger = logging.getLogger(__name__)

def decode_email_header(header):
    """Decodes email headers to a readable string."""
    if not header:
        return ""
    decoded_parts = decode_header(header)
    header_parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                header_parts.append(part.decode(charset or 'utf-8', errors='ignore'))
            except (LookupError, TypeError):
                header_parts.append(part.decode('utf-8', errors='ignore'))
        else:
            header_parts.append(str(part))
    return "".join(header_parts)


@shared_task(name="email_inbox.fetch_new_emails")
def fetch_new_emails():
    """
    Fetches new emails via IMAP and passes them to the Service.
    """
    if not all([settings.IMAP_HOST, settings.IMAP_USER, settings.IMAP_PASSWORD]):
        logger.warning("IMAP settings are not configured. Skipping.")
        return "Skipped: Missing credentials."

    mail = None
    try:
        # 1. Connect to IMAP
        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        mail.select("inbox")

        # 2. Search for Unread Emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return "Failed to search for emails."

        email_ids = messages[0].split()
        if not email_ids:
            return "No new emails found."
            
        logger.info(f"Found {len(email_ids)} new emails.")

        service = EmailInboxService()
        processed_count = 0

        for email_id in email_ids:
            try:
                # 3. Fetch the Raw Email
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email_bytes = msg_data[0][1]
                msg = email.message_from_bytes(raw_email_bytes)

                # 4. Parse Headers
                subject = decode_email_header(msg.get("Subject", "(No Subject)"))
                from_header = decode_email_header(msg.get("From", ""))
                from_name, from_email_addr = email.utils.parseaddr(from_header)
                
                # Parse To/CC safely
                to_header = decode_email_header(msg.get("To", ""))
                cc_header = decode_email_header(msg.get("Cc", ""))
                to_emails = [addr[1] for addr in email.utils.getaddresses([to_header]) if addr[1]]
                cc_emails = [addr[1] for addr in email.utils.getaddresses([cc_header]) if addr[1]]

                # 5. Extract Content & Attachments
                text_content = ""
                html_content = ""
                attachments_data = []

                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    # A. Extract Text/HTML Body
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        charset = part.get_content_charset() or 'utf-8'
                        text_content += part.get_payload(decode=True).decode(charset, errors='ignore')
                    
                    elif content_type == "text/html" and "attachment" not in content_disposition:
                        charset = part.get_content_charset() or 'utf-8'
                        html_content += part.get_payload(decode=True).decode(charset, errors='ignore')
                    
                    # B. Extract Attachments
                    elif "attachment" in content_disposition or part.get_filename():
                        filename = part.get_filename()
                        if filename:
                            filename = decode_email_header(filename)
                            file_data = part.get_payload(decode=True)
                            
                            # Save to Media Storage (so Service can link it)
                            # We use a temp folder structure: email_attachments/YYYY/MM/uuid/file
                            file_path = f"email_attachments/incoming/{filename}"
                            saved_path = default_storage.save(file_path, ContentFile(file_data))
                            
                            attachments_data.append({
                                "filename": filename,
                                "content_type": content_type,
                                "file_size": len(file_data),
                                "file_path": saved_path,
                                "is_safe": True # Assume safe or add virus scanning logic here
                            })

                # 6. Pass to Service
                service.receive_email(
                    from_email=from_email_addr,
                    from_name=from_name,
                    to_email=to_emails[0] if to_emails else settings.IMAP_USER,
                    cc_emails=cc_emails,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    attachments=attachments_data, # Now passing real data
                    raw_headers=dict(msg.items()),
                    raw_body=raw_email_bytes.decode('utf-8', errors='ignore')
                )
                processed_count += 1

                # 7. Mark as Seen (CRITICAL: Prevents infinite loop)
                # Only mark as seen if processing succeeded
                mail.store(email_id, '+FLAGS', '\\Seen')

            except Exception as e:
                logger.error(f"Error processing email ID {email_id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"IMAP connection failed: {e}", exc_info=True)
    finally:
        # 8. Close Safely
        if mail:
            try:
                if mail.state == 'SELECTED':
                    mail.close()
                mail.logout()
            except:
                pass

    return f"Processed {processed_count} emails."