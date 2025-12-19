import imaplib
import smtplib
import email
import logging
import uuid
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from django.conf import settings
from django.utils import timezone
from django.template import Template, Context
from celery import shared_task

# Imports from Settings App
from apps.email_settings.models import EmailAccount, EmailModuleSettings
from apps.email_settings.utils import decrypt_credential

# Imports from Inbox App
from .models import BulkEmailCampaign, EmailInboxMessage, EmailFolder
from .services import EmailInboxService

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def generate_pdf_from_html(html_content, context_data):
    try:
        import weasyprint
        return weasyprint.HTML(string=html_content).write_pdf()
    except ImportError:
        return f"Document Content:\n\n{html_content}".encode('utf-8')

def decode_email_header(header):
    if not header: return ""
    decoded_parts = decode_header(header)
    header_parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                header_parts.append(part.decode(charset or 'utf-8', errors='ignore'))
            except:
                header_parts.append(part.decode('utf-8', errors='ignore'))
        else:
            header_parts.append(str(part))
    return "".join(header_parts)

def extract_body(msg, content_type_pref):
    content = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == f"text/{content_type_pref}" and "attachment" not in str(part.get("Content-Disposition")):
                charset = part.get_content_charset() or 'utf-8'
                try:
                    content = part.get_payload(decode=True).decode(charset, errors='ignore')
                    break
                except: pass
    else:
        if msg.get_content_type() == f"text/{content_type_pref}":
            charset = msg.get_content_charset() or 'utf-8'
            try:
                content = msg.get_payload(decode=True).decode(charset, errors='ignore')
            except: pass
    return content

def get_sending_configuration(account):
    """
    Determines the correct SMTP/API credentials based on the Account's 'sending_method'.
    """
    config = {
        'from_email': account.email_address,
        'use_tls': True
    }

    # OPTION A: Use Account's own SMTP
    if account.sending_method == 'smtp':
        config.update({
            'host': account.smtp_server,
            'port': account.smtp_port,
            'username': account.email_address,
            'password': decrypt_credential(account.access_credential)
        })
        config['use_tls'] = account.use_ssl_tls
        return config

    # OPTION B & C: Use a Provider
    # NOTE: Ensure this matches your actual app name for providers
    from apps.email_provider.models import EmailProviderConfig 
    
    provider = None
    if account.sending_method == 'specific_provider':
        provider = account.specific_provider
    elif account.sending_method == 'system_default':
        provider = EmailProviderConfig.objects.filter(is_default=True).first()

    if not provider:
        raise ValueError(f"No provider found for sending method: {account.sending_method}")

    # Map Provider fields to config
    config.update({
        'host': provider.smtp_host,
        'port': provider.smtp_port,
        'username': provider.smtp_username, 
        'password': provider.smtp_password 
    })
    
    return config

def send_email_with_config(config, to_email, subject, html_body, attachments):
    """
    Generic sender that works with the config dictionary.
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config['from_email']
        msg['To'] = to_email
        
        msg.attach(MIMEText(html_body, 'html'))
        
        for att in attachments:
            part = MIMEApplication(att['content'], Name=att['name'])
            part['Content-Disposition'] = f'attachment; filename="{att["name"]}"'
            msg.attach(part)

        server = smtplib.SMTP(config['host'], config['port'])
        if config.get('use_tls'):
            server.starttls()
            
        server.login(config['username'], config['password'])
        server.sendmail(config['from_email'], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"SMTP Error: {e}")
        return False

def process_imap_folder(mail, folder_name, is_incoming, account, service):
    # ... (Keep your existing IMAP folder processing logic here) ...
    # (It looks correct in your snippet)
    try:
        mail.select(folder_name)
        status, messages = mail.search(None, 'UNSEEN')
        if status != "OK" or not messages[0]: return 0

        email_ids = messages[0].split()
        count = 0
        for email_id in email_ids:
            try:
                _, msg_data = mail.fetch(email_id, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = decode_email_header(msg.get("Subject", "(No Subject)"))
                from_header = decode_email_header(msg.get("From", ""))
                from_name, from_email_addr = email.utils.parseaddr(from_header)
                
                service.receive_email(
                    from_email=from_email_addr,
                    from_name=from_name,
                    to_email=account.email_address,
                    subject=subject,
                    html_content=extract_body(msg, 'html'),
                    text_content=extract_body(msg, 'plain'),
                    folder_type_override='inbox' if is_incoming else 'sent'
                )
                count += 1
            except Exception as e:
                logger.error(f"Error parsing email {email_id}: {e}")
        return count
    except Exception as e:
        return 0

# ==========================================
# TASKS
# ==========================================

@shared_task(name="apps.email_inbox.tasks.fetch_new_emails")
def fetch_new_emails():
    """Loops through ALL defined accounts and fetches emails."""
    accounts = EmailAccount.objects.filter(is_deleted=False, auto_sync_enabled=True)
    total_synced = 0
    service = EmailInboxService()

    for account in accounts:
        try:
            password = decrypt_credential(account.access_credential)
            if not password: continue

            mail = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
            mail.login(account.email_address, password)
            
            count = process_imap_folder(mail, "INBOX", is_incoming=True, account=account, service=service)
            total_synced += count
            mail.logout()
            
            account.last_sync_at = timezone.now()
            account.connection_status = True
            account.save(update_fields=['last_sync_at', 'connection_status'])
        except Exception as e:
            account.connection_status = False
            account.last_sync_log = str(e)
            account.save(update_fields=['connection_status', 'last_sync_log'])

    return f"Synced {total_synced} emails."

@shared_task(name="apps.email_inbox.tasks.send_campaign_emails")
def send_campaign_emails(campaign_id):
    """Sends emails for a campaign with Smart Configuration."""
    try:
        campaign = BulkEmailCampaign.objects.get(id=campaign_id)
        if campaign.status in ['processing', 'completed']: return "Already processed"

        campaign.status = 'processing'
        campaign.save(update_fields=['status'])
        
        # 1. Find Sender Account
        sender_account = EmailAccount.objects.filter(user=campaign.created_by, is_deleted=False).first()
        if not sender_account:
            campaign.status = 'failed'
            campaign.save()
            return "No sending account found."

        # 2. Get Configuration (Smart Logic)
        try:
            smtp_config = get_sending_configuration(sender_account)
        except Exception as e:
            logger.error(f"Configuration Error: {e}")
            campaign.status = 'failed'
            campaign.save()
            return f"Config failed: {e}"

        # Settings
        module_settings = EmailModuleSettings.objects.filter(user=campaign.created_by).first()
        auto_gen_docs = module_settings.auto_generate_documents if module_settings else False
        attach_docs = module_settings.attach_to_emails if module_settings else False

        success_count = 0
        fail_count = 0
        
        base_subject = campaign.custom_subject if campaign.custom_subject else campaign.subject_template
        base_body = campaign.body_html_template

        for recipient in campaign.recipients_data:
            try:
                # Data Mapping
                if 'name' in recipient and 'customer_name' not in recipient:
                    recipient['customer_name'] = recipient['name']
                if 'company_name' not in recipient:
                    recipient['company_name'] = "RenewIQ"

                # Mail Merge
                ctx = Context(recipient)
                final_subject = Template(base_subject).render(ctx)
                body_content = Template(base_body).render(ctx)
                
                # Attachments
                attachments = []
                if auto_gen_docs and attach_docs:
                    pdf_bytes = generate_pdf_from_html(body_content, recipient)
                    doc_name = f"Policy_{recipient.get('policy_number', 'Doc')}.pdf"
                    attachments.append({'name': doc_name, 'content': pdf_bytes, 'content_type': 'application/pdf'})

                # Save to DB (Sent Items)
                EmailInboxMessage.objects.create(
                    from_email=sender_account.email_address,
                    to_emails=[recipient.get('email')],
                    subject=final_subject,
                    html_content=body_content,
                    text_content=body_content, 
                    folder=EmailFolder.objects.get_or_create(folder_type='sent', defaults={'name':'Sent', 'is_system':True})[0],
                    status='read',
                    message_id=str(uuid.uuid4()),
                    category='marketing',
                    created_by=campaign.created_by
                )

                # Send using Config
                if send_email_with_config(smtp_config, recipient.get('email'), final_subject, body_content, attachments):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Error sending to {recipient.get('email')}: {e}")
                fail_count += 1
                continue

        campaign.status = 'completed'
        campaign.successful_sends = success_count
        campaign.failed_sends = fail_count
        campaign.sent_at = timezone.now()
        campaign.save()
        
    except BulkEmailCampaign.DoesNotExist:
        pass

@shared_task(name="apps.email_inbox.tasks.process_scheduled_campaigns")
def process_scheduled_campaigns():
    """Checks for campaigns that are scheduled for now or the past."""
    now = timezone.now()
    due_campaigns = BulkEmailCampaign.objects.filter(
        status='scheduled',
        scheduled_at__lte=now
    )
    
    count = 0
    for campaign in due_campaigns:
        send_campaign_emails.delay(campaign.id)
        count += 1
        
    return f"Triggered {count} campaigns"