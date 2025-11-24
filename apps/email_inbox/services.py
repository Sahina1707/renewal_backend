import logging
import re
from typing import List, Dict, Any, Optional
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db.models import Q, Count, F, Avg
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery
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
                     attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Receive and process an incoming email
        
        Args:
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content
            from_name: Sender name
            cc_emails: CC email addresses
            bcc_emails: BCC email addresses
            reply_to: Reply-to email address
            raw_headers: Raw email headers
            raw_body: Raw email body
            attachments: List of attachment data
        
        Returns:
            Dict with success status and message details
        """
        try:
            # Create email message
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
                message_id=str(uuid.uuid4()),
                thread_id=str(uuid.uuid4()),
                in_reply_to='',
                references='',
                is_spam=False,
                is_phishing=False,
                subcategory='reply',
                confidence_score=0.0,
                attachments=[],
                attachment_count=0,
                headers={},
                size_bytes=0,
                source='webhook',
                source_message_id=str(uuid.uuid4())
            )
            
            # Classify email
            self._classify_email(email_message)
            
            # Apply filters
            self._apply_filters(email_message)
            
            # Process attachments
            if attachments:
                self._process_attachments(email_message, attachments)
            
            # Update conversation thread
            self._update_conversation_thread(email_message)
            
            # --- NEW CODE: Trigger the Rules Engine ---
            try:
                # We import here to avoid circular dependency issues
                from apps.email_integration.services import EmailIntegrationService
                integration_service = EmailIntegrationService()
                
                # Trigger automations for "email_received"
                integration_service.trigger_automations(
                    trigger_type='email_received', 
                    context_data={
                        'email_id': str(email_message.id),
                        'sender': email_message.from_email,
                        'subject': email_message.subject,
                        'body': email_message.text_content or email_message.html_content
                    }
                )
            except (ImportError, ModuleNotFoundError):
                logger.warning("EmailIntegrationService not found. Skipping automations.")
            except Exception as e:
                logger.error(f"Failed to run automations for email {email_message.id}: {e}")

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
        """Classify email based on content and sender"""
        try:
            subject = email_message.subject.lower()
            content = (email_message.text_content or email_message.html_content or '').lower()
            
            # Policy renewal keywords
            renewal_keywords = ['renewal', 'renew', 'expire', 'expiry', 'expiring']
            if any(keyword in subject or keyword in content for keyword in renewal_keywords):
                email_message.category = 'policy_renewal'
                email_message.priority = 'high'
            
            # Claim keywords
            elif any(keyword in subject or keyword in content for keyword in ['claim', 'claims', 'accident', 'damage', 'loss']):
                email_message.category = 'claim'
                email_message.priority = 'high'
            
            # Payment keywords
            elif any(keyword in subject or keyword in content for keyword in ['payment', 'premium', 'bill', 'invoice', 'due']):
                email_message.category = 'payment'
                email_message.priority = 'normal'
            
            # Complaint keywords
            elif any(keyword in subject or keyword in content for keyword in ['complaint', 'unhappy', 'dissatisfied', 'problem', 'issue']):
                email_message.category = 'complaint'
                email_message.priority = 'high'
                email_message.sentiment = 'negative'
            
            # Inquiry keywords
            elif any(keyword in subject or keyword in content for keyword in ['question', 'inquiry', 'help', 'information', 'query']):
                email_message.category = 'inquiry'
                email_message.priority = 'normal'
            
            # Thank you keywords
            elif any(keyword in subject or keyword in content for keyword in ['thank', 'thanks', 'appreciate', 'grateful']):
                email_message.category = 'feedback'
                email_message.sentiment = 'positive'
                email_message.priority = 'low'
            
            else:
                email_message.category = 'general'
                email_message.priority = 'normal'
            
            # Determine sentiment if not already set
            if email_message.sentiment == 'neutral':
                positive_words = ['good', 'great', 'excellent', 'happy', 'satisfied', 'pleased']
                negative_words = ['bad', 'terrible', 'awful', 'angry', 'frustrated', 'disappointed']
                
                if any(word in content for word in positive_words):
                    email_message.sentiment = 'positive'
                elif any(word in content for word in negative_words):
                    email_message.sentiment = 'negative'
            
            email_message.save()
            
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
        Actually sends the email via SMTP/Gmail/Outlook
        """
        try:
            # 1. Setup Email
            subject = email_message_obj.subject
            body_html = email_message_obj.html_content or email_message_obj.text_content
            from_email = settings.DEFAULT_FROM_EMAIL
            to_emails = email_message_obj.to_emails # Assuming this is a list in your JSONField
            
            # 2. Create Message Object
            msg = EmailMultiAlternatives(
                subject=subject,
                body=email_message_obj.text_content or "Please view this email in an HTML compatible viewer.",
                from_email=from_email,
                to=to_emails,
                cc=email_message_obj.cc_emails,
                bcc=email_message_obj.bcc_emails,
                reply_to=[email_message_obj.reply_to] if email_message_obj.reply_to else None
            )
            
            # 3. Attach HTML alternative
            if body_html:
                msg.attach_alternative(body_html, "text/html")

            # 4. Handle Attachments (If passed during creation)
            if attachments:
                for file in attachments:
                    # file is an InMemoryUploadedFile from request.FILES
                    msg.attach(file.name, file.read(), file.content_type)

            # 5. Send
            msg.send()
            
            return True, "Sent successfully"

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, str(e)
    
    def reply_to_email(self, email_id: str, subject: str, html_content: str = '',
                      text_content: str = '', to_emails: List[str] = None,
                      cc_emails: List[str] = None, bcc_emails: List[str] = None,
                      priority: str = 'normal', tags: List[str] = None) -> Dict[str, Any]:
        """Reply to an email"""
        try:
            original_email = EmailInboxMessage.objects.get(id=email_id)
            
            # Create reply message
            reply_message = EmailInboxMessage(
                from_email=original_email.to_emails[0] if original_email.to_emails else settings.DEFAULT_FROM_EMAIL,
                to_emails=[original_email.from_email] + (to_emails or []),
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                category=original_email.category,
                priority=priority,
                status='unread', # Temp status
                thread_id=original_email.thread_id,
                parent_message=original_email,
                tags=tags or [],
                message_id=str(uuid.uuid4())
            )
            
            # Send the actual email
            success, error_msg = self.send_outbound_email(reply_message)
            
            if not success:
                return {'success': False, 'message': f'Failed to send reply: {error_msg}'}
            
            # Mark original as replied
            original_email.mark_as_replied()
            
            return {
                'success': True,
                'message': 'Reply sent successfully',
                'reply_id': str(reply_message.id)
            }
            
        except EmailInboxMessage.DoesNotExist:
            return {
                'success': False,
                'message': 'Original email not found'
            }
        except Exception as e:
            logger.error(f"Error replying to email: {str(e)}")
            return {
                'success': False,
                'message': f'Error replying to email: {str(e)}'
            }
    
    def forward_email(self, email_id: str, to_emails: List[str], subject: str = None,
                     message: str = '', cc_emails: List[str] = None,
                     bcc_emails: List[str] = None, priority: str = 'normal',
                     tags: List[str] = None) -> Dict[str, Any]:
        """Forward an email"""
        try:
            original_email = EmailInboxMessage.objects.get(id=email_id)
            
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
                status='unread', # Temp status
                tags=tags or [],
                message_id=str(uuid.uuid4())
            )
            
            # Send the actual email
            success, error_msg = self.send_outbound_email(forward_message)

            if not success:
                return {'success': False, 'message': f'Failed to send forward: {error_msg}'}

            # Mark original as forwarded
            original_email.mark_as_forwarded()
            
            return {
                'success': True,
                'message': 'Email forwarded successfully',
                'forward_id': str(forward_message.id)
            }
            
        except EmailInboxMessage.DoesNotExist:
            return {
                'success': False,
                'message': 'Original email not found'
            }
        except Exception as e:
            logger.error(f"Error forwarding email: {str(e)}")
            return {
                'success': False,
                'message': f'Error forwarding email: {str(e)}'
            }
    
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
    
    def get_email_statistics(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get email inbox statistics"""
        try:
            # Build filter
            filters = {'is_deleted': False}
            if start_date:
                filters['received_at__gte'] = start_date
            if end_date:
                filters['received_at__lte'] = end_date
            
            # Get basic counts
            emails = EmailInboxMessage.objects.filter(**filters)
            
            total_emails = emails.count()
            unread_emails = emails.filter(status='unread').count()
            read_emails = emails.filter(status='read').count()
            starred_emails = emails.filter(is_starred=True).count()
            important_emails = emails.filter(is_important=True).count()
            
            # Get counts by status
            emails_by_status = {}
            for status, _ in EmailInboxMessage.STATUS_CHOICES:
                count = emails.filter(status=status).count()
                if count > 0:
                    emails_by_status[status] = count
            
            # Get counts by category
            emails_by_category = {}
            for category, _ in EmailInboxMessage.CATEGORY_CHOICES:
                count = emails.filter(category=category).count()
                if count > 0:
                    emails_by_category[category] = count
            
            # Get counts by priority
            emails_by_priority = {}
            for priority, _ in EmailInboxMessage.PRIORITY_CHOICES:
                count = emails.filter(priority=priority).count()
                if count > 0:
                    emails_by_priority[priority] = count
            
            # Get counts by sentiment
            emails_by_sentiment = {}
            for sentiment, _ in EmailInboxMessage.SENTIMENT_CHOICES:
                count = emails.filter(sentiment=sentiment).count()
                if count > 0:
                    emails_by_sentiment[sentiment] = count
            
            # Get counts by folder
            emails_by_folder = {}
            folder_data = emails.values('folder__name').annotate(
                count=Count('id')
            ).filter(folder__isnull=False)
            for item in folder_data:
                emails_by_folder[item['folder__name']] = item['count']
            
            # Get recent activity
            recent_activity = emails.order_by('-received_at')[:10].values(
                'id', 'subject', 'from_email', 'status', 'received_at'
            )
            
            # Get top senders
            top_senders = emails.values('from_email').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Get response time statistics
            replied_emails = emails.filter(status='replied', replied_at__isnull=False)
            response_times = []
            for email in replied_emails:
                if email.replied_at and email.received_at:
                    response_time = (email.replied_at - email.received_at).total_seconds() / 3600  # hours
                    response_times.append(response_time)
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            return {
                'total_emails': total_emails,
                'unread_emails': unread_emails,
                'read_emails': read_emails,
                'starred_emails': starred_emails,
                'important_emails': important_emails,
                'emails_by_status': emails_by_status,
                'emails_by_category': emails_by_category,
                'emails_by_priority': emails_by_priority,
                'emails_by_sentiment': emails_by_sentiment,
                'emails_by_folder': emails_by_folder,
                'recent_activity': list(recent_activity),
                'top_senders': list(top_senders),
                'response_time_stats': {
                    'average_response_time_hours': round(avg_response_time, 2),
                    'total_replied_emails': len(response_times)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting email statistics: {str(e)}")
            return {
                'error': f'Error getting email statistics: {str(e)}'
            }
