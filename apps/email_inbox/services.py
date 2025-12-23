import logging
import re
from typing import List, Dict, Any, Optional
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Case, When, Value, FloatField, Avg, Count, Q, F,Sum
from django.utils import timezone
from datetime import timedelta
import uuid
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from apps.email_settings.models import EmailAccount
from apps.email_settings.utils import decrypt_credential
from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery,BulkEmailCampaign
)

logger = logging.getLogger(__name__)


class EmailInboxService:
    """Service for managing email inbox operations"""
    
    def __init__(self):
        pass
    
    def receive_email(self, from_email: str, to_email: str, subject: str,
                      html_content: str = '', text_content: str = '',
                      from_name: str = None, cc_emails: List[str] = None,
                      bcc_emails: List[str] = None, reply_to: str = None,
                      raw_headers: Dict[str, Any] = None, raw_body: str = None,
                      attachments: List[Dict[str, Any]] = None,
                      folder_type_override: str = 'inbox', source: str = 'webhook',
                      message_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            final_message_id = message_id or str(uuid.uuid4())
            if EmailInboxMessage.objects.filter(message_id=final_message_id).exists():
                logger.info(f"Skipping duplicate email with Message-ID: {final_message_id}")
                return {'success': True, 'message': 'Email already exists', 'skipped': True}

            target_folder, _ = EmailFolder.objects.get_or_create(
                folder_type=folder_type_override,
                defaults={
                    'name': folder_type_override.capitalize(), 
                    'is_system': True
                }
            )

            email_message = EmailInboxMessage.objects.create(
                from_email=from_email,
                from_name=from_name,
                to_emails=[to_email] if to_email else [],
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                reply_to=reply_to or '',
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                message_id=final_message_id,
                thread_id=str(uuid.uuid4()),
                folder=target_folder,
                status='read' if folder_type_override == 'sent' else 'unread',
                source=source,
                attachments=[],
                attachment_count=0,
                headers={},
                size_bytes=0,
                source_message_id=str(uuid.uuid4())
            )
            
            # (Rest of the logic remains the same...)
            self._classify_email(email_message)
            self._apply_filters(email_message)
            if attachments:
                self._process_attachments(email_message, attachments)
            self._update_conversation_thread(email_message)
            
            # ... (Keep the automation trigger logic) ...

            return {
                'success': True,
                'message': 'Email received and processed successfully',
                'email_id': str(email_message.id),
                'category': email_message.category,
                'priority': email_message.priority,
                'sentiment': email_message.sentiment
            }
            
        except Exception as e:
            logger.error(f"Error receiving email: {str(e)}")
            return {
                'success': False,
                'message': f'Error receiving email: {str(e)}'
            }
    
    def _classify_email(self, email_message: EmailInboxMessage):
        """
        Auto-tags emails based on your Dashboard Categories:
        Refund, Complaint, Appointment, Feedback, Uncategorized.
        """
        try:
            subject = email_message.subject.lower()
            content = (email_message.text_content or email_message.html_content or '').lower()
            text = f"{subject} {content}"
            
            # Default
            category = 'uncategorized'
            priority = 'normal'
            sentiment = 'neutral'

            # 1. Refund (Yellow)
            if any(w in text for w in ['refund', 'money back', 'reimbursement', 'wrong charge', 'deducted']):
                category = 'refund'
                priority = 'high'
            
            # 2. Complaint (Red)
            elif any(w in text for w in ['complaint', 'angry', 'issue', 'bad service', 'fail', 'disappointed']):
                category = 'complaint'
                priority = 'high'
                sentiment = 'negative'

            # 3. Appointment (Green)
            elif any(w in text for w in ['appointment', 'schedule', 'meeting', 'book a call', 'visit', 'calendar']):
                category = 'appointment'
                priority = 'normal'

            # 4. Feedback (Blue)
            elif any(w in text for w in ['feedback', 'review', 'suggestion', 'opinion', 'rate', 'star']):
                category = 'feedback'
                priority = 'low'
                sentiment = 'positive'

            # Save Classification
            email_message.category = category
            email_message.priority = priority
            email_message.sentiment = sentiment
            email_message.save(update_fields=['category', 'priority', 'sentiment'])
            
        except Exception as e:
            logger.error(f"Error classifying email: {str(e)}")


    def _apply_filters(self, email_message: EmailInboxMessage):
        """Apply email filters to the message"""
        try:
            filters = EmailFilter.objects.filter(
                is_active=True,
                is_deleted=False
            ).order_by('-priority')
            
            for filter_obj in filters:
                if self._matches_filter(email_message, filter_obj):
                    self._apply_filter_action(email_message, filter_obj)
                    filter_obj.match_count += 1
                    filter_obj.last_matched = timezone.now()
                    filter_obj.save(update_fields=['match_count', 'last_matched'])
                    break  # Apply only the first matching filter
            
        except Exception as e:
            logger.error(f"Error applying filters: {str(e)}")
    
    def _matches_filter(self, email_message: EmailInboxMessage, filter_obj: EmailFilter) -> bool:
        """Check if email message matches filter criteria"""
        try:
            if filter_obj.filter_type == 'subject':
                text = email_message.subject
            elif filter_obj.filter_type == 'from':
                text = email_message.from_email
            elif filter_obj.filter_type == 'to':
                text = email_message.to_email
            elif filter_obj.filter_type == 'body':
                text = email_message.text_content or email_message.html_content or ''
            elif filter_obj.filter_type == 'category':
                text = email_message.category
            elif filter_obj.filter_type == 'priority':
                text = email_message.priority
            else:
                return False
            
            text = text.lower()
            value = filter_obj.value.lower()
            
            if filter_obj.operator == 'contains':
                return value in text
            elif filter_obj.operator == 'not_contains':
                return value not in text
            elif filter_obj.operator == 'equals':
                return text == value
            elif filter_obj.operator == 'not_equals':
                return text != value
            elif filter_obj.operator == 'starts_with':
                return text.startswith(value)
            elif filter_obj.operator == 'ends_with':
                return text.endswith(value)
            elif filter_obj.operator == 'regex':
                return bool(re.search(value, text))
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching filter: {str(e)}")
            return False
    
    def _apply_filter_action(self, email_message: EmailInboxMessage, filter_obj: EmailFilter):
        """Apply filter action to email message"""
        try:
            if filter_obj.action == 'move_to_folder':
                if filter_obj.action_value:
                    folder = EmailFolder.objects.get(id=filter_obj.action_value)
                    email_message.folder = folder
            
            elif filter_obj.action == 'mark_as_read':
                email_message.status = 'read'
                email_message.read_at = timezone.now()
            
            elif filter_obj.action == 'mark_as_important':
                email_message.is_important = True
            
            elif filter_obj.action == 'add_tag':
                if filter_obj.action_value:
                    if filter_obj.action_value not in email_message.tags:
                        email_message.tags.append(filter_obj.action_value)
            
            elif filter_obj.action == 'assign_to':
                if filter_obj.action_value:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(id=filter_obj.action_value)
                    email_message.assigned_to = user
            
            email_message.save()
            
        except Exception as e:
            logger.error(f"Error applying filter action: {str(e)}")
    
    def _process_attachments(self, email_message: EmailInboxMessage, attachments: List[Dict[str, Any]]):
        """Process email attachments"""
        try:
            for attachment_data in attachments:
                EmailAttachment.objects.create(
                    email_message=email_message,
                    filename=attachment_data.get('filename', ''),
                    content_type=attachment_data.get('content_type', 'application/octet-stream'),
                    file_size=attachment_data.get('file_size', 0),
                    file_path=attachment_data.get('file_path', ''),
                    is_safe=attachment_data.get('is_safe', True),
                    scan_result=attachment_data.get('scan_result', {})
                )
        except Exception as e:
            logger.error(f"Error processing attachments: {str(e)}")
    
    def _update_conversation_thread(self, email_message: EmailInboxMessage):
        """Update conversation thread for email message"""
        try:
            # Extract thread ID from subject (simple implementation)
            thread_id = self._extract_thread_id(email_message.subject)
            
            if thread_id:
                email_message.thread_id = thread_id
                email_message.save()
                
                # Update or create conversation
                conversation, created = EmailConversation.objects.get_or_create(
                    thread_id=thread_id,
                    defaults={
                        'subject': email_message.subject,
                        'participants': [email_message.from_email, email_message.to_email],
                        'last_message_at': email_message.received_at,
                        'last_message_from': email_message.from_email
                    }
                )
                
                if not created:
                    # Update existing conversation
                    conversation.message_count += 1
                    if email_message.status == 'unread':
                        conversation.unread_count += 1
                    conversation.last_message_at = email_message.received_at
                    conversation.last_message_from = email_message.from_email
                    
                    # Update participants
                    participants = set(conversation.participants)
                    participants.add(email_message.from_email)
                    participants.add(email_message.to_email)
                    conversation.participants = list(participants)
                    
                    conversation.save()
            
        except Exception as e:
            logger.error(f"Error updating conversation thread: {str(e)}")
    
    def _extract_thread_id(self, subject: str) -> str:
        """Extract thread ID from email subject"""
        # Simple implementation - look for "Re:" or "Fwd:" patterns
        if subject.lower().startswith(('re:', 'fwd:')):
            # Remove "Re:" or "Fwd:" and use the rest as thread ID
            return subject[4:].strip()
        return None
    
    def send_outbound_email(self, email_message_obj, attachments=None):
        """
        Sends email using the SPECIFIC SMTP credentials of the sender account.
        Includes safety cleaning for CC/BCC to prevent delivery failures.
        """
        try:
            # 1. Identify Sender Account
            sender_address = email_message_obj.from_email
            
            account = EmailAccount.objects.filter(
                email_address__iexact=sender_address, 
                is_deleted=False
            ).first()

            if not account:
                logger.warning(f"No EmailAccount found for {sender_address}. Using default backend.")
                return self._send_via_django_backend(email_message_obj, attachments)

            # 2. Decrypt Credentials
            password = decrypt_credential(account.access_credential)
            if not password:
                return False, "Account has no password saved."

            # 3. CLEAN RECIPIENT LISTS (The Fix)
            # Ensure we don't have None, empty strings, or duplicates
            def clean_list(recipients):
                if not recipients: return []
                if isinstance(recipients, str): return [recipients]
                # Filter out None and empty strings
                return [r.strip() for r in recipients if r and isinstance(r, str) and r.strip()]

            to_list = clean_list(email_message_obj.to_emails)
            cc_list = clean_list(email_message_obj.cc_emails)
            bcc_list = clean_list(email_message_obj.bcc_emails)

            if not to_list:
                return False, "No valid 'To' recipients found."

            # 4. Construct the Email (MIME)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email_message_obj.subject
            msg['From'] = f"{account.account_name} <{account.email_address}>"
            msg['To'] = ", ".join(to_list)
            
            if cc_list:
                msg['Cc'] = ", ".join(cc_list)
            
            if email_message_obj.reply_to:
                msg['Reply-To'] = email_message_obj.reply_to

            # Attach Body
            body_html = email_message_obj.html_content or email_message_obj.text_content
            body_text = email_message_obj.text_content or "Please view in HTML."
            
            msg.attach(MIMEText(body_text, 'plain'))
            if body_html:
                msg.attach(MIMEText(body_html, 'html'))

            # 5. Handle Attachments
            if attachments:
                for file in attachments:
                    try:
                        if hasattr(file, 'read'): # UploadedFile
                            content = file.read()
                            name = file.name
                        elif isinstance(file, dict): # Dictionary
                            content = file['content']
                            name = file['name']
                        else:
                            continue

                        part = MIMEApplication(content, Name=name)
                        part['Content-Disposition'] = f'attachment; filename="{name}"'
                        msg.attach(part)
                    except Exception as e:
                        logger.error(f"Attachment error: {e}")

            # 6. CONNECT & SEND
            if account.use_ssl_tls and account.smtp_port == 465:
                server = smtplib.SMTP_SSL(account.smtp_server, account.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(account.smtp_server, account.smtp_port, timeout=10)
                if account.use_ssl_tls:
                    server.starttls()

            server.login(account.email_address, password)
            
            # Combine all recipients for the Envelope (To + CC + BCC)
            # Use set() to remove duplicates (e.g. if I CC myself)
            all_recipients = list(set(to_list + cc_list + bcc_list))
            
            logger.info(f"Sending email from {account.email_address} to {all_recipients}")
            
            server.sendmail(account.email_address, all_recipients, msg.as_string())
            server.quit()
            
            return True, "Sent successfully via SMTP"

        except Exception as e:
            logger.error(f"Failed to send email via {email_message_obj.from_email}: {e}")
            return False, str(e)

    def _send_via_django_backend(self, email_message_obj, attachments=None):
        """Fallback method using standard Django settings"""
        try:
            msg = EmailMultiAlternatives(
                subject=email_message_obj.subject,
                body=email_message_obj.text_content,
                from_email=settings.DEFAULT_FROM_EMAIL, # Fallback only
                to=email_message_obj.to_emails,
                cc=email_message_obj.cc_emails,
                bcc=email_message_obj.bcc_emails,
                reply_to=[email_message_obj.reply_to] if email_message_obj.reply_to else None
            )
            if email_message_obj.html_content:
                msg.attach_alternative(email_message_obj.html_content, "text/html")
            msg.send()
            return True, "Sent via default backend"
        except Exception as e:
            return False, str(e)
    def reply_to_email(self, email_id: str, subject: str, html_content: str = '',
                       text_content: str = '', to_emails: List[str] = None,
                       cc_emails: List[str] = None, bcc_emails: List[str] = None,
                       priority: str = 'normal', tags: List[str] = None) -> Dict[str, Any]:
        """Reply to an email with Smart Account Detection"""
        try:
            original_email = EmailInboxMessage.objects.get(id=email_id)
            
            # --- FIX 1: SMART ACCOUNT DETECTION ---
            # We need to find which of our accounts received this email so we can reply FROM it.
            our_account_email = None
            
            # Check all recipients in the original email 'To' list
            potential_emails = original_email.to_emails or []
            if isinstance(potential_emails, str): potential_emails = [potential_emails]
            
            for recipient in potential_emails:
                if EmailAccount.objects.filter(email_address__iexact=recipient, is_deleted=False).exists():
                    our_account_email = recipient
                    break # Found one of our accounts!
            
            # If still not found, check CC list
            if not our_account_email and original_email.cc_emails:
                for recipient in original_email.cc_emails:
                    if EmailAccount.objects.filter(email_address__iexact=recipient, is_deleted=False).exists():
                        our_account_email = recipient
                        break

            # Fallback: Use the Default Sender Account if we couldn't match the incoming email
            if not our_account_email:
                default_account = EmailAccount.objects.filter(is_default_sender=True, is_deleted=False).first()
                if default_account:
                    our_account_email = default_account.email_address
                else:
                    # Last Resort: Use the logged in user's account if available, or system default
                    # (This prevents the empty {} error by ensuring we have SOME string)
                    our_account_email = settings.DEFAULT_FROM_EMAIL

            # --- FIX 2: CREATE REPLY MESSAGE ---
            sent_folder, _ = EmailFolder.objects.get_or_create(
                folder_type='sent',
                defaults={'name': 'Sent', 'is_system': True}
            )

            reply_message = EmailInboxMessage(
                from_email=our_account_email,  # Now guaranteed to be a valid string
                to_emails=to_emails or [original_email.from_email], # Default reply to sender
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                category=original_email.category,
                priority=priority,
                status='read',        
                folder=sent_folder,   
                thread_id=original_email.thread_id,
                parent_message=original_email,
                tags=tags or [],
                message_id=str(uuid.uuid4()),
                created_by=original_email.assigned_to # Or current user if context available
            )
            
            # Save BEFORE sending to ensure ID exists
            reply_message.save()

            # --- FIX 3: SEND WITH DETAILED ERROR LOGGING ---
            success, error_msg = self.send_outbound_email(reply_message)
            
            if not success:
                # Update status to failed so we can see it in UI
                reply_message.status = 'failed'
                reply_message.save()
                return {'success': False, 'message': f'Failed to send reply via {our_account_email}: {error_msg}'}
            
            # Mark original as replied
            original_email.mark_as_replied()
            
            # Update reply status
            reply_message.sent_at = timezone.now()
            reply_message.save()
            
            return {
                'success': True,
                'message': 'Reply sent successfully',
                'reply_id': str(reply_message.id)
            }
            
        except EmailInboxMessage.DoesNotExist:
            return {'success': False, 'message': 'Original email not found'}
        except Exception as e:
            logger.error(f"Error replying to email: {str(e)}")
            return {'success': False, 'message': f'Error replying to email: {str(e)}'}
            
    def forward_email(self, email_id: str, to_emails: List[str], subject: str = None,
                      message: str = '', cc_emails: List[str] = None,
                      bcc_emails: List[str] = None, priority: str = 'normal',
                      tags: List[str] = None) -> Dict[str, Any]:
        """Forward an email"""
        try:
            original_email = EmailInboxMessage.objects.get(id=email_id)
            
            # --- FIX: Get Sent Folder ---
            sent_folder, _ = EmailFolder.objects.get_or_create(
                folder_type='sent',
                defaults={'name': 'Sent', 'is_system': True}
            )

            # Create forward message
            forward_subject = subject or f"Fwd: {original_email.subject}"
            forward_message = EmailInboxMessage(
                from_email=original_email.to_emails[0] if original_email.to_emails else settings.DEFAULT_FROM_EMAIL,
                to_emails=to_emails,
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                subject=forward_subject,
                html_content=f"{message}<br><hr><br>{original_email.html_content}",
                text_content=f"{message}\n---\n{original_email.text_content}",
                category=original_email.category,
                priority=priority,
                status='read',        # <--- Outgoing mail is always 'read'
                folder=sent_folder,   # <--- ASSIGN TO SENT FOLDER
                tags=tags or [],
                message_id=str(uuid.uuid4())
            )
            
            # Send the actual email
            success, error_msg = self.send_outbound_email(forward_message)

            if not success:
                return {'success': False, 'message': f'Failed to send forward: {error_msg}'}

            # --- FIX: SAVE TO DATABASE ---
            forward_message.save() # <--- CRITICAL! This was missing.

            # Mark original as forwarded
            original_email.mark_as_forwarded()
            
            return {
                'success': True,
                'message': 'Email forwarded successfully',
                'forward_id': str(forward_message.id)
            }
            
        except EmailInboxMessage.DoesNotExist:
            return {'success': False, 'message': 'Original email not found'}
        except Exception as e:
            logger.error(f"Error forwarding email: {str(e)}")
            return {'success': False, 'message': f'Error forwarding email: {str(e)}'}
    
    def search_emails(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Search emails based on query parameters"""
        try:
            queryset = EmailInboxMessage.objects.filter(is_deleted=False)
            
            # Apply filters
            if query_params.get('query'):
                search_query = query_params['query']
                queryset = queryset.filter(
                    Q(subject__icontains=search_query) |
                    Q(from_email__icontains=search_query) |
                    Q(to_email__icontains=search_query) |
                    Q(text_content__icontains=search_query) |
                    Q(html_content__icontains=search_query)
                )
            
            if query_params.get('folder_id'):
                queryset = queryset.filter(folder_id=query_params['folder_id'])
            
            if query_params.get('category'):
                queryset = queryset.filter(category=query_params['category'])
            
            if query_params.get('priority'):
                queryset = queryset.filter(priority=query_params['priority'])
            
            if query_params.get('status'):
                queryset = queryset.filter(status=query_params['status'])
            
            if query_params.get('sentiment'):
                queryset = queryset.filter(sentiment=query_params['sentiment'])
            
            if query_params.get('from_email'):
                queryset = queryset.filter(from_email__icontains=query_params['from_email'])
            
            if query_params.get('to_email'):
                queryset = queryset.filter(to_email__icontains=query_params['to_email'])
            
            if query_params.get('assigned_to'):
                queryset = queryset.filter(assigned_to_id=query_params['assigned_to'])
            
            if query_params.get('is_starred') is not None:
                queryset = queryset.filter(is_starred=query_params['is_starred'])
            
            if query_params.get('is_important') is not None:
                queryset = queryset.filter(is_important=query_params['is_important'])
            
            if query_params.get('has_attachments') is not None:
                if query_params['has_attachments']:
                    queryset = queryset.filter(attachments__isnull=False).distinct()
                else:
                    queryset = queryset.filter(attachments__isnull=True)
            
            if query_params.get('start_date'):
                queryset = queryset.filter(received_at__gte=query_params['start_date'])
            
            if query_params.get('end_date'):
                queryset = queryset.filter(received_at__lte=query_params['end_date'])
            
            if query_params.get('tags'):
                for tag in query_params['tags']:
                    queryset = queryset.filter(tags__contains=[tag])
            
            # Apply sorting
            sort_by = query_params.get('sort_by', 'received_at')
            sort_order = query_params.get('sort_order', 'desc')
            
            if sort_order == 'desc':
                sort_by = f'-{sort_by}'
            
            queryset = queryset.order_by(sort_by)
            
            # Apply pagination
            page = query_params.get('page', 1)
            page_size = query_params.get('page_size', 20)
            start = (page - 1) * page_size
            end = start + page_size
            
            emails = queryset[start:end]
            total_count = queryset.count()
            
            return {
                'success': True,
                'emails': emails,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return {
                'success': False,
                'message': f'Error searching emails: {str(e)}'
            }
    
    def get_dashboard_summary(self, user):
        today = timezone.now().date()
        emails = EmailInboxMessage.objects.filter(is_deleted=False)
        
        # 1. Top Cards Data
        total_today = emails.filter(received_at__date=today).count()
        new_unread = emails.filter(status='unread').count()
        in_progress = emails.filter(status__in=['read', 'replied']).count()
        
        # 2. SLA Breaches (Due Date passed)
        sla_breaches = emails.filter(
            due_date__lt=timezone.now(),
            status__in=['unread', 'read']
        ).count()

        # 3. Categorized Breakdown (For Colored Buttons)
        # We initialize with 0 so the frontend always gets all keys
        categories = {
            "complaint": 0,
            "feedback": 0,
            "refund": 0,
            "appointment": 0,
            "uncategorized": 0
        }
        
        # Fill with actual DB counts
        db_counts = emails.values('category').annotate(count=Count('id'))
        for item in db_counts:
            cat_key = item['category']
            if cat_key in categories:
                categories[cat_key] = item['count']

        return {
            "total_today": total_today,
            "new_emails": new_unread,
            "in_progress": in_progress,
            "sla_breaches": sla_breaches,
            "categories": categories, # Use this object to populate the buttons
            "sla_alert_message": f"{sla_breaches} emails have breached SLA requirements"
        }
    
    def get_full_analytics_report(self, start_date=None, end_date=None):
        email_filters = {'is_deleted': False}
        campaign_filters = {}
        
        if start_date:
            email_filters['received_at__gte'] = start_date
            campaign_filters['created_at__gte'] = start_date
            
        if end_date:
            email_filters['received_at__lte'] = end_date
            campaign_filters['created_at__lte'] = end_date
        
        emails = EmailInboxMessage.objects.filter(**email_filters)
        campaigns = BulkEmailCampaign.objects.filter(**campaign_filters)

        # A. General Stats
        total_emails = emails.count()
        resolved_count = emails.filter(status__in=['resolved', 'closed']).count()
        
        # Calculate Global Average Response Time
        global_replied = emails.filter(replied_at__isnull=False, received_at__isnull=False)
        global_avg_hours = 0.0
        if global_replied.exists():
            # Sum total seconds and convert to hours
            total_seconds = sum((e.replied_at - e.received_at).total_seconds() for e in global_replied)
            global_avg_hours = round((total_seconds / global_replied.count()) / 3600, 1)
        
        # Satisfaction Score
        sat_agg = emails.aggregate(
            score=Avg(Case(
                When(sentiment='positive', then=Value(5.0)),
                When(sentiment='neutral', then=Value(3.0)),
                When(sentiment='negative', then=Value(1.0)),
                output_field=FloatField()
            ))
        )
        satisfaction = round(sat_agg['score'] or 0, 1)

        # B. Agent Performance
        User = get_user_model()
        agents = User.objects.filter(is_active=True) 
        
        agent_performance = []
        for agent in agents:
            # 1. Emails Assigned
            assigned_msgs = emails.filter(assigned_to=agent)
            
            if not assigned_msgs.exists():

                pass

            # 2. Emails Handled (Replied or Resolved)
            handled = assigned_msgs.filter(status__in=['replied', 'resolved']).count()
            total = assigned_msgs.count()
            
            # 3. Response Time (Only for emails with a reply)
            replied_msgs = assigned_msgs.filter(replied_at__isnull=False, received_at__isnull=False)
            avg_hours = 0.0
            if replied_msgs.exists():
                total_seconds = sum((e.replied_at - e.received_at).total_seconds() for e in replied_msgs)
                avg_hours = round((total_seconds / replied_msgs.count()) / 3600, 1)

            res_rate = round((handled / total * 100), 1) if total > 0 else 0
            
            efficiency = "Average"
            if res_rate > 90: efficiency = "Excellent"
            elif res_rate > 75: efficiency = "Good"

            agent_performance.append({
                "agent_name": agent.get_full_name() or agent.username,
                "emails_handled": handled,
                "avg_response_time": f"{avg_hours} hours",
                "resolution_rate": res_rate,
                "customer_rating": 4.5, 
                "efficiency": efficiency
            })

        # C. Campaign Stats (THE FIX)
        total_campaigns = campaigns.count()
        
        # Aggregates
        agg_stats = campaigns.aggregate(
            recipients=Sum('total_recipients'),
            success=Sum('successful_sends'),
            opened=Sum('opened_count'),
            clicked=Sum('clicked_count')
        )
        
        t_recipients = agg_stats['recipients'] or 0
        t_success = agg_stats['success'] or 0
        t_opened = agg_stats['opened'] or 0
        t_clicked = agg_stats['clicked'] or 0
        
        # Calculate Rates
        avg_delivery = round((t_success / t_recipients * 100), 1) if t_recipients > 0 else 0
        avg_open_rate = round((t_opened / t_success * 100), 1) if t_success > 0 else 0
        avg_click_rate = round((t_clicked / t_opened * 100), 1) if t_opened > 0 else 0

        # Recent Campaigns List
        recent_campaigns_list = []
        for camp in campaigns.order_by('-created_at')[:5]:
            # Per Campaign Open Rate
            c_open = round((camp.opened_count / camp.successful_sends * 100), 1) if camp.successful_sends > 0 else 0
            c_click = round((camp.clicked_count / camp.opened_count * 100), 1) if camp.opened_count > 0 else 0
            
            recent_campaigns_list.append({
                "name": camp.name,
                "date": camp.created_at.strftime("%Y-%m-%d"),
                "recipients": camp.total_recipients,
                "delivered": camp.successful_sends,
                "opened": camp.opened_count,
                "clicked": camp.clicked_count,
                "open_rate": c_open,
                "click_rate": c_click
            })

        return {
            "summary": {
                "total_emails": total_emails,
                "resolved": resolved_count,
                "avg_response_time": f"{global_avg_hours} hours",
                "satisfaction": satisfaction
            },
            "agent_performance": agent_performance,
            "campaign_performance": {
                "total_campaigns": total_campaigns,
                "total_recipients": t_recipients,
                "avg_delivery_rate": avg_delivery,
                "avg_open_rate": avg_open_rate,      
                "avg_click_rate": avg_click_rate,    
                "recent_campaigns": recent_campaigns_list
            }
        }