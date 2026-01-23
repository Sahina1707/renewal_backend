import logging
from typing import List, Dict, Any, Optional
from django.utils import timezone
from datetime import date
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from .models import EmailMessage, EmailQueue, EmailTracking, EmailDeliveryReport, EmailAnalytics
from apps.email_provider.services import EmailProviderService

logger = logging.getLogger(__name__)


class EmailOperationsService:
    """Service for managing email operations"""
    
    def __init__(self):
        self.provider_service = EmailProviderService()
    
    def _enhance_email_content_for_deliverability(self, html_content: str, text_content: str, subject: str) -> tuple:
        """
        Enhance email content to improve deliverability and avoid spam filters
        Always enhance content to make it look professional and avoid spam
        """
        if not html_content or html_content.strip() == '':
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h2 style="color: #2c3e50; margin-top: 0;">Welleazy Team</h2>
                    <p style="margin: 0; color: #666;">Your trusted insurance partner</p>
                </div>
                
                <div style="background-color: white; padding: 20px; border: 1px solid #e9ecef; border-radius: 8px;">
                    <p>{text_content or "Thank you for your interest in our services."}</p>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 8px; font-size: 12px; color: #666;">
                    <p style="margin: 0 0 10px 0;"><strong>Welleazy Insurance Services</strong></p>
                    <p style="margin: 0 0 5px 0;">1st Floor, 9th Main Rd, next to The Anandam Cafe</p>
                    <p style="margin: 0 0 5px 0;">7th Sector, HSR Layout, Bangalore, India</p>
                    <p style="margin: 0 0 10px 0;">Email: support@welleazy.com | Phone: +91-XXXX-XXXX</p>
                    <p style="margin: 0; font-size: 11px;">
                        <a href="https://welleazy.com/unsubscribe" style="color: #666; text-decoration: none;">Unsubscribe</a> | 
                        <a href="https://welleazy.com/privacy" style="color: #666; text-decoration: none;">Privacy Policy</a>
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h2 style="color: #2c3e50; margin-top: 0;">Welleazy Team</h2>
                    <p style="margin: 0; color: #666;">Your trusted insurance partner</p>
                </div>
                
                <div style="background-color: white; padding: 20px; border: 1px solid #e9ecef; border-radius: 8px;">
                    <html><body style='font-family: Arial, sans-serif; color: #333;'>\n  <h2 style='color:#2E86C1;'>Policy Renewal Reminder</h2>\n  <p>Dear Customer,</p>\n  <p>Your policy with <b>Welleazy</b> is due for renewal. To continue enjoying uninterrupted services, please renew your policy before the due date.</p>\n  <table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; margin: 10px 0;'>\n    <tr><td><b>Policy No:</b></td><td>WLZ-123456</td></tr>\n    <tr><td><b>Renewal Amount:</b></td><td>₹4,500</td></tr>\n    <tr><td><b>Due Date:</b></td><td>25th September 2025</td></tr>\n  </table>\n  <p><a href='https://welleazy.com/renewal' style='background:#2E86C1; color:#fff; padding:10px 20px; text-decoration:none; border-radius:5px;'>Renew Now</a></p>\n  <p>For any queries, write to <a href='mailto:support@welleazy.com'>support@welleazy.com</a> or call <b>1800-123-456</b>.</p>\n  <br>\n  <p>Thank you,<br>Welleazy Team</p>\n</body></html>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 8px; font-size: 12px; color: #666;">
                    <p style="margin: 0 0 10px 0;"><strong>Welleazy Insurance Services</strong></p>
                    <p style="margin: 0 0 5px 0;">1st Floor, 9th Main Rd, next to The Anandam Cafe</p>
                    <p style="margin: 0 0 5px 0;">7th Sector, HSR Layout, Bangalore, India</p>
                    <p style="margin: 0 0 10px 0;">Email: support@welleazy.com | Phone: +91-XXXX-XXXX</p>
                    <p style="margin: 0; font-size: 11px;">
                        <a href="https://welleazy.com/unsubscribe" style="color: #666; text-decoration: none;">Unsubscribe</a> | 
                        <a href="https://welleazy.com/privacy" style="color: #666; text-decoration: none;">Privacy Policy</a>
                    </p>
                </div>
            </body>
            </html>
            """
        
        if not text_content or text_content.strip() == '':
            text_content = """
Welleazy Team
Your trusted insurance partner

Thank you for your interest in our services.

---
Welleazy Insurance Services
1st Floor, 9th Main Rd, next to The Anandam Cafe
7th Sector, HSR Layout, Bangalore, India
Email: support@welleazy.com | Phone: +91-XXXX-XXXX

Unsubscribe: https://welleazy.com/unsubscribe
Privacy Policy: https://welleazy.com/privacy
            """.strip()
        else:
            text_content = f"""
Welleazy Team
Your trusted insurance partner

{text_content}

---
Welleazy Insurance Services
1st Floor, 9th Main Rd, next to The Anandam Cafe
7th Sector, HSR Layout, Bangalore, India
Email: support@welleazy.com | Phone: +91-XXXX-XXXX

Unsubscribe: https://welleazy.com/unsubscribe
Privacy Policy: https://welleazy.com/privacy
            """.strip()
        
        return html_content, text_content

    def send_email(self, to_emails: str, subject: str, html_content: str = '',
                   text_content: str = '', template_id: str = None,
                   template_variables: Dict[str, Any] = None, from_email: str = None,
                   from_name: str = None, reply_to: str = None, cc_emails: List[str] = None,
                   bcc_emails: List[str] = None, priority: str = 'normal',
                   scheduled_at: str = None, campaign_id: str = None,
                   tags: List[str] = None) -> Dict[str, Any]:
        """
        Send a single email
        
        Args:
            to_emails: Recipient email address
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content
            template_id: ID of email template to use
            template_variables: Variables for template rendering
            from_email: Sender email address
            from_name: Sender name
            reply_to: Reply-to email address
            cc_emails: CC email addresses
            bcc_emails: BCC email addresses
            priority: Email priority
            scheduled_at: When to send the email (ISO format)
            campaign_id: Campaign identifier
            tags: Tags for categorization
        
        Returns:
            Dict with success status and message details
        """
        try:
            import uuid
            message_id = f"msg_{uuid.uuid4().hex[:12]}_{int(timezone.now().timestamp())}"
            
            enhanced_html, enhanced_text = self._enhance_email_content_for_deliverability(
                html_content, text_content, subject
            )
            
            if not reply_to:
                try:
                    from apps.email_provider.models import EmailProviderConfig
                    provider = EmailProviderConfig.objects.filter(
                        is_active=True, 
                        health_status='healthy'
                    ).order_by('priority').first()
                    if provider and provider.reply_to:
                        reply_to = provider.reply_to
                except:
                    pass
            
            email_message = EmailMessage.objects.create(
                message_id=message_id,
                to_emails=to_emails,
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                from_name=from_name,
                reply_to=reply_to,
                subject=subject,
                html_content=enhanced_html,
                text_content=enhanced_text,
                template_id=template_id,
                template_variables=template_variables or {},
                priority=priority,
                scheduled_at=scheduled_at,
                campaign_id=campaign_id,
                tags=tags or [],
                created_by=None
            )
            
            # If scheduled for future, add to queue
            if scheduled_at and timezone.datetime.fromisoformat(scheduled_at.replace('Z', '+00:00')) > timezone.now():
                EmailQueue.objects.create(
                    email_message=email_message,
                    priority=priority,
                    scheduled_for=scheduled_at
                )
                return {
                    'success': True,
                    'message': 'Email scheduled successfully',
                    'email_id': str(email_message.id),
                    'scheduled_at': scheduled_at
                }
            
            result = self._send_email_message(email_message)
            
            return {
                'success': result['success'],
                'message': result.get('message', 'Email sent successfully' if result['success'] else 'Email sending failed'),
                'email_id': str(email_message.id),
                'provider_name': result.get('provider_name'),
                'response_time': result.get('response_time')
            }
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending email: {str(e)}'
            }
    
    def send_bulk_emails(self, to_emails: List[str], subject: str, html_content: str = '',
                        text_content: str = '', template_id: str = None,
                        template_variables: Dict[str, Any] = None, from_email: str = None,
                        from_name: str = None, reply_to: str = None, cc_emails: List[str] = None,
                        bcc_emails: List[str] = None, priority: str = 'normal',
                        campaign_id: str = None, tags: List[str] = None) -> Dict[str, Any]:
        """
        Send bulk emails
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content
            template_id: ID of email template to use
            template_variables: Variables for template rendering
            from_email: Sender email address
            from_name: Sender name
            reply_to: Reply-to email address
            cc_emails: CC email addresses
            bcc_emails: BCC email addresses
            priority: Email priority
            campaign_id: Campaign identifier
            tags: Tags for categorization
        
        Returns:
            Dict with success status and bulk operation details
        """
        try:
            success_count = 0
            failure_count = 0
            email_ids = []
            
            for to_email in to_emails:
                try:
                    result = self.send_email(
                        to_emails=to_email,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                        template_id=template_id,
                        template_variables=template_variables,
                        from_email=from_email,
                        from_name=from_name,
                        reply_to=reply_to,
                        cc_emails=cc_emails,
                        bcc_emails=bcc_emails,
                        priority=priority,
                        campaign_id=campaign_id,
                        tags=tags
                    )
                    
                    if result['success']:
                        success_count += 1
                        email_ids.append(result['email_id'])
                    else:
                        failure_count += 1
                        
                except Exception as e:
                    logger.error(f"Error sending email to {to_email}: {str(e)}")
                    failure_count += 1
            
            return {
                'success': failure_count == 0,
                'message': f'Bulk email operation completed. Success: {success_count}, Failures: {failure_count}',
                'success_count': success_count,
                'failure_count': failure_count,
                'total_count': len(to_emails),
                'email_ids': email_ids
            }
            
        except Exception as e:
            logger.error(f"Error in bulk email sending: {str(e)}")
            return {
                'success': False,
                'message': f'Error in bulk email sending: {str(e)}'
            }
    
    def schedule_email(self, to_emails: str, subject: str, scheduled_at: str,
                      html_content: str = '', text_content: str = '',
                      template_id: str = None, template_variables: Dict[str, Any] = None,
                      from_email: str = None, from_name: str = None, reply_to: str = None,
                      cc_emails: List[str] = None, bcc_emails: List[str] = None,
                      priority: str = 'normal', campaign_id: str = None,
                      tags: List[str] = None) -> Dict[str, Any]:
        """
        Schedule an email for future sending
        
        Args:
            to_emails: Recipient email address
            subject: Email subject
            scheduled_at: When to send the email (ISO format)
            html_content: HTML content
            text_content: Plain text content
            template_id: ID of email template to use
            template_variables: Variables for template rendering
            from_email: Sender email address
            from_name: Sender name
            reply_to: Reply-to email address
            cc_emails: CC email addresses
            bcc_emails: BCC email addresses
            priority: Email priority
            campaign_id: Campaign identifier
            tags: Tags for categorization
        
        Returns:
            Dict with success status and scheduling details
        """
        try:
            # Create email message record
            email_message = EmailMessage.objects.create(
                to_emails=to_emails,
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                from_name=from_name,
                reply_to=reply_to,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                template_id=template_id,
                template_variables=template_variables or {},
                priority=priority,
                scheduled_at=scheduled_at,
                campaign_id=campaign_id,
                tags=tags or [],
                created_by=None
            )
            
            # Add to queue
            EmailQueue.objects.create(
                email_message=email_message,
                priority=priority,
                scheduled_for=scheduled_at
            )
            
            return {
                'success': True,
                'message': 'Email scheduled successfully',
                'email_id': str(email_message.id),
                'scheduled_at': scheduled_at
            }
            
        except Exception as e:
            logger.error(f"Error scheduling email: {str(e)}")
            return {
                'success': False,
                'message': f'Error scheduling email: {str(e)}'
            }
    
    def _send_email_message(self, email_message: EmailMessage) -> Dict[str, Any]:
        """Send an email message using the provider service"""
        try:
            # Try to send via provider service first
            result = self.provider_service.send_email(
                to_emails=[email_message.to_emails],
                subject=email_message.subject,
                html_content=email_message.html_content or '',
                text_content=email_message.text_content or '',
                from_email=email_message.from_email,
                from_name=email_message.from_name,
                reply_to=email_message.reply_to,
                cc_emails=email_message.cc_emails,
                bcc_emails=email_message.bcc_emails
            )
            
            if result['success']:
                # Update email message
                email_message.status = 'sent'
                email_message.sent_at = timezone.now()
                email_message.provider_name = result.get('provider_name')
                email_message.provider_message_id = result.get('message_id')
                email_message.save()
                
                # Create tracking event
                EmailTracking.objects.create(
                    email_message=email_message,
                    event_type='sent',
                    event_data={'provider': result.get('provider_name')}
                )
                
                return result
            else:
                # Update email message with error (no fallback)
                email_message.status = 'failed'
                email_message.error_message = result.get('error', 'Unknown error')
                email_message.retry_count += 1
                email_message.save()
                
                return result
                
        except Exception as e:
            logger.error(f"Provider service failed: {str(e)}")
            
            # Update email message with error (no fallback)
            email_message.status = 'failed'
            email_message.error_message = str(e)
            email_message.retry_count += 1
            email_message.save()
            
            return {
                'success': False,
                'error': str(e),
                'provider_name': 'SendGrid'
            }
    
    def _send_via_django_fallback(self, email_message: EmailMessage) -> Dict[str, Any]:
        """
        Fallback method using Django's built-in email backend
        """
        try:
            # Create email message
            msg = EmailMultiAlternatives(
                subject=email_message.subject,
                body=email_message.text_content or email_message.html_content,
                from_email=email_message.from_email or settings.DEFAULT_FROM_EMAIL,
                to=[email_message.to_emails],
                cc=email_message.cc_emails or [],
                bcc=email_message.bcc_emails or []
            )

            # Add HTML content if available
            if email_message.html_content:
                msg.attach_alternative(email_message.html_content, "text/html")

            # Send email
            msg.send()

            return {
                'success': True,
                'provider_name': 'Django SMTP Fallback',
                'message_id': f'django_{email_message.message_id}',
                'response_time': 0.1
            }

        except Exception as e:
            logger.error(f"Django fallback failed: {str(e)}")
            return {
                'success': False,
                'error': f"Django fallback failed: {str(e)}",
                'provider_name': 'Django SMTP Fallback'
            }
    
    def process_email_queue(self) -> Dict[str, Any]:
        """Process pending emails in the queue"""
        try:
            # Get pending emails that are ready to be sent
            pending_emails = EmailQueue.objects.filter(
                status='queued',
                scheduled_for__lte=timezone.now()
            ).order_by('priority', 'scheduled_for')[:100]  # Process up to 100 emails at a time
            
            processed_count = 0
            success_count = 0
            failure_count = 0
            
            for queue_entry in pending_emails:
                try:
                    # Update queue status
                    queue_entry.status = 'processing'
                    queue_entry.attempts += 1
                    queue_entry.save()
                    
                    # Send email
                    result = self._send_email_message(queue_entry.email_message)
                    
                    if result['success']:
                        queue_entry.status = 'sent'
                        queue_entry.processed_at = timezone.now()
                        success_count += 1
                    else:
                        if queue_entry.attempts >= queue_entry.max_attempts:
                            queue_entry.status = 'failed'
                            queue_entry.last_error = result.get('error', 'Max retries exceeded')
                            failure_count += 1
                        else:
                            # Reschedule for retry
                            queue_entry.status = 'queued'
                            queue_entry.scheduled_for = timezone.now() + timezone.timedelta(minutes=5)
                    
                    queue_entry.save()
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing queue entry {queue_entry.id}: {str(e)}")
                    queue_entry.status = 'failed'
                    queue_entry.last_error = str(e)
                    queue_entry.save()
                    failure_count += 1
                    processed_count += 1
            
            return {
                'success': True,
                'message': f'Processed {processed_count} emails. Success: {success_count}, Failures: {failure_count}',
                'processed_count': processed_count,
                'success_count': success_count,
                'failure_count': failure_count
            }
            
        except Exception as e:
            logger.error(f"Error processing email queue: {str(e)}")
            return {
                'success': False,
                'message': f'Error processing email queue: {str(e)}'
            }
    
    def get_email_statistics(self, start_date: str = None, end_date: str = None,
                           campaign_id: str = None) -> Dict[str, Any]:
        """Get email statistics for a given period"""
        try:
            # Build filter
            filters = {}
            if start_date:
                filters['created_at__gte'] = start_date
            if end_date:
                filters['created_at__lte'] = end_date
            if campaign_id:
                filters['campaign_id'] = campaign_id
            
            # Get email counts
            emails = EmailMessage.objects.filter(**filters)
            
            total_emails = emails.count()
            sent_emails = emails.filter(status='sent').count()
            delivered_emails = emails.filter(status='delivered').count()
            failed_emails = emails.filter(status='failed').count()
            pending_emails = emails.filter(status__in=['pending', 'sending']).count()
            
            # Calculate rates
            delivery_rate = (delivered_emails / sent_emails * 100) if sent_emails > 0 else 0
            
            # Get tracking data
            tracking_events = EmailTracking.objects.filter(
                email_message__in=emails
            )
            
            opened_emails = tracking_events.filter(event_type='opened').values('email_message').distinct().count()
            clicked_emails = tracking_events.filter(event_type='clicked').values('email_message').distinct().count()
            bounced_emails = tracking_events.filter(event_type='bounced').values('email_message').distinct().count()
            
            open_rate = (opened_emails / delivered_emails * 100) if delivered_emails > 0 else 0
            click_rate = (clicked_emails / delivered_emails * 100) if delivered_emails > 0 else 0
            bounce_rate = (bounced_emails / sent_emails * 100) if sent_emails > 0 else 0
            
            # Get average response time
            delivery_reports = EmailDeliveryReport.objects.filter(
                email_message__in=emails,
                response_time__isnull=False
            )
            avg_response_time = delivery_reports.aggregate(
                avg_time=models.Avg('response_time')
            )['avg_time'] or 0
            
            # Get emails by status
            emails_by_status = {}
            for status, _ in EmailMessage.STATUS_CHOICES:
                count = emails.filter(status=status).count()
                if count > 0:
                    emails_by_status[status] = count
            
            # Get emails by priority
            emails_by_priority = {}
            for priority, _ in EmailMessage.PRIORITY_CHOICES:
                count = emails.filter(priority=priority).count()
                if count > 0:
                    emails_by_priority[priority] = count
            
            # Get emails by campaign
            emails_by_campaign = {}
            campaign_data = emails.values('campaign_id').annotate(
                count=models.Count('id')
            ).filter(campaign_id__isnull=False)
            for item in campaign_data:
                emails_by_campaign[item['campaign_id']] = item['count']
            
            # Get recent activity
            recent_activity = emails.order_by('-created_at')[:10].values(
                'id', 'subject', 'to_emails', 'status', 'created_at'
            )
            
            return {
                'total_emails': total_emails,
                'sent_emails': sent_emails,
                'delivered_emails': delivered_emails,
                'failed_emails': failed_emails,
                'pending_emails': pending_emails,
                'delivery_rate': round(delivery_rate, 2),
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2),
                'bounce_rate': round(bounce_rate, 2),
                'avg_response_time': round(avg_response_time, 3),
                'emails_by_status': emails_by_status,
                'emails_by_priority': emails_by_priority,
                'emails_by_campaign': emails_by_campaign,
                'recent_activity': list(recent_activity)
            }
            
        except Exception as e:
            logger.error(f"Error getting email statistics: {str(e)}")
            return {
                'error': f'Error getting email statistics: {str(e)}'
            }
    
    def update_email_status(self, email_id: str, status: str, 
                          provider_message_id: str = None, error_message: str = None) -> Dict[str, Any]:
        """Update email status (typically called by webhooks)"""
        try:
            email_message = EmailMessage.objects.get(id=email_id)
            
            # Update status
            email_message.status = status
            if provider_message_id:
                email_message.provider_message_id = provider_message_id
            if error_message:
                email_message.error_message = error_message
            if status == 'sent':
                email_message.sent_at = timezone.now()
            
            email_message.save()
            
            # Create tracking event
            EmailTracking.objects.create(
                email_message=email_message,
                event_type=status,
                event_data={'provider_message_id': provider_message_id}
            )
            
            return {
                'success': True,
                'message': f'Email status updated to {status}'
            }
            
        except EmailMessage.DoesNotExist:
            return {
                'success': False,
                'message': 'Email not found'
            }
        except Exception as e:
            logger.error(f"Error updating email status: {str(e)}")
            return {
                'success': False,
                'message': f'Error updating email status: {str(e)}'
            }
