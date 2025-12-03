import imaplib
import email
import requests
from email.header import decode_header
from django.utils import timezone
from dateutil import parser
from .models import EmailAccount, EmailMessage, ClassificationRule, EmailModuleSettings
from .utils import normalize_and_get_credential

class EmailSyncService:
    def sync_account(self, account_id):
        """
        Connects to a specific account and fetches new emails.
        """
        account = EmailAccount.objects.get(id=account_id)
        credential = normalize_and_get_credential(account)
        
        if not credential:
            return {"success": False, "error": "No credentials found"}

        try:
            # 1. Connect to IMAP
            mail = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
            mail.login(account.email_address, credential)
            mail.select("INBOX")

            # 2. Search for UNREAD messages
            # (Fetching only unread keeps it fast. Remove 'UNSEEN' to fetch all if needed)
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()

            synced_count = 0
            
            for e_id in email_ids:
                # Fetch the email body (RFC822)
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        self._process_and_save_email(account, msg)
                        synced_count += 1
            
            mail.logout()
            
            # Update account status
            account.last_sync_at = timezone.now()
            account.last_sync_log = f"Successfully synced {synced_count} messages."
            account.connection_status = True
            account.save()
            
            return {"success": True, "count": synced_count}

        except Exception as e:
            account.connection_status = False
            account.last_sync_log = str(e)
            account.save()
            return {"success": False, "error": str(e)}

    def _process_and_save_email(self, account, msg):
        """
        Parses raw email bytes and saves to DB.
        """
        # 1. Extract Headers
        subject = self._decode_str(msg["Subject"])
        sender = self._decode_str(msg.get("From"))
        message_id = msg.get("Message-ID", "").strip()
        
        # Avoid duplicates
        if EmailMessage.objects.filter(message_id=message_id).exists():
            return

        # 2. Extract Body
        body_text = ""
        body_html = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                try:
                    payload = part.get_payload(decode=True)
                    if payload and "attachment" not in content_disposition:
                        if content_type == "text/plain":
                            body_text += payload.decode(errors="ignore")
                        elif content_type == "text/html":
                            body_html += payload.decode(errors="ignore")
                except:
                    pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if msg.get_content_type() == "text/html":
                    body_html = payload.decode(errors="ignore")
                else:
                    body_text = payload.decode(errors="ignore")
            except:
                pass

        # 3. Apply Classification Rules (Simple Keyword Match)
        category = 'uncategorized'
        priority = 'medium'
        
        # Check database rules for this user
        rules = ClassificationRule.objects.filter(user=account.user, is_enabled=True)
        search_text = (subject + " " + body_text).lower()
        
        for rule in rules:
            if rule.keyword.lower() in search_text:
                category = rule.category
                priority = rule.priority
                break  # Stop at first match

        email_obj = EmailMessage.objects.create(
            email_account=account,
            message_id=message_id,
            subject=subject[:900], 
            sender=sender,
            received_at=timezone.now(), 
            body_text=body_text,
            body_html=body_html,
            category=category,
            priority=priority,
            is_read=False
        )
        
        # --- NEW: TRIGGER WEBHOOK AFTER SAVING ---
        self._send_webhook_notification(email_obj, account.user)

    def _send_webhook_notification(self, email_obj, user):
        """
        Checks settings and sends a POST request to the external URL if enabled.
        """
        try:
            # 1. Load Settings
            settings = EmailModuleSettings.objects.filter(user=user).first()
            
            # 2. Check if enabled
            if not settings or not settings.enable_webhook_notifications or not settings.webhook_url:
                return # Feature disabled or URL missing

            # 3. Prepare Payload
            payload = {
                "event": "new_email_received",
                "account_name": email_obj.email_account.account_name,
                "email_id": email_obj.id,
                "remote_message_id": email_obj.message_id,
                "subject": email_obj.subject,
                "sender": email_obj.sender,
                "received_at": email_obj.received_at.isoformat(),
                "classification": {
                    "category": email_obj.category,
                    "priority": email_obj.priority
                },
                "snippet": email_obj.body_text[:200] # Send a preview
            }

            # 4. Fire the Webhook (Timeout is important so we don't hang the sync)
            print(f"🚀 Triggering Webhook to: {settings.webhook_url}")
            response = requests.post(settings.webhook_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                print("✅ Webhook delivered successfully.")
            else:
                print(f"⚠️ Webhook failed with status: {response.status_code}")

        except Exception as e:
            # Log error but DO NOT crash the sync process
            print(f"❌ Webhook Error: {str(e)}")

    def _decode_str(self, header_val):
        """Helper to decode MIME headers (e.g., =?utf-8?Q?...)"""
        if not header_val: return ""
        decoded_list = decode_header(header_val)
        result = ""
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                if encoding:
                    try:
                        result += content.decode(encoding)
                    except:
                        result += content.decode('utf-8', errors='ignore')
                else:
                    result += content.decode('utf-8', errors='ignore')
            else:
                result += str(content)
        return result