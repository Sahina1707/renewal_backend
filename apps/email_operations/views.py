from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import models
from django.db.models import Q, Count, F
from django.utils import timezone
from datetime import timedelta, date

from .models import EmailMessage, EmailQueue, EmailTracking, EmailDeliveryReport, EmailAnalytics
from .serializers import (
    EmailMessageSerializer, EmailMessageCreateSerializer, EmailMessageUpdateSerializer,
    EmailQueueSerializer, EmailTrackingSerializer, EmailDeliveryReportSerializer,
    EmailAnalyticsSerializer, BulkEmailSerializer, ScheduledEmailSerializer,
    EmailStatsSerializer, EmailCampaignStatsSerializer, SentEmailListSerializer
)
from .services import EmailOperationsService


class EmailMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email messages"""
    
    queryset = EmailMessage.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EmailMessageCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EmailMessageUpdateSerializer
        return EmailMessageSerializer
    
    def get_queryset(self):
        """Filter email messages based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by campaign
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        # Filter by template
        template_id = self.request.query_params.get('template_id')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        # Filter by recipient
        to_email = self.request.query_params.get('to_email')
        if to_email:
            queryset = queryset.filter(to_emails__icontains=to_email)
        
        # Filter by sender
        from_email = self.request.query_params.get('from_email')
        if from_email:
            queryset = queryset.filter(from_email__icontains=from_email)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Search by subject
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(subject__icontains=search)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new email message"""
        serializer.save(created_by=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Override create to return simple success response"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        # Send the email using the service
        result = service.send_email(**serializer.validated_data)
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Email service result: {result}")
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Email sent successfully',
                'data': {
                    'to_emails': serializer.validated_data.get('to_emails'),
                    'subject': serializer.validated_data.get('subject'),
                    'status': 'sent'
                }
            }, status=status.HTTP_201_CREATED)
        else:
            # Get the actual error message from the result
            error_message = result.get('error', 'Unknown error')
            if not error_message or error_message == 'Unknown error':
                error_message = result.get('message', 'Failed to send email')
            
            return Response({
                'success': False,
                'message': 'Failed to send email',
                'error': error_message
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def perform_update(self, serializer):
        """Set updated_by when updating an email message"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the email message"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=False, methods=['post'])
    def send_bulk(self, request):
        """Send bulk emails"""
        serializer = BulkEmailSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        result = service.send_bulk_emails(**serializer.validated_data)
        
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a single email immediately"""
        serializer = EmailMessageCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        # Send the email using the service
        result = service.send_email(**serializer.validated_data)
        
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send_simple(self, request):
        """Send a simple email with minimal required fields"""
        # Extract only the essential fields
        to_emails = request.data.get('to_emails')
        subject = request.data.get('subject')
        html_content = request.data.get('html_content')
        text_content = request.data.get('text_content')
        
        # Validate required fields
        if not to_emails:
            return Response(
                {'error': 'to_emails is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not subject:
            return Response(
                {'error': 'subject is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not html_content and not text_content:
            return Response(
                {'error': 'Either html_content or text_content is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare email data with defaults (only supported parameters)
        email_data = {
            'to_emails': to_emails,
            'subject': subject,
            'html_content': html_content or '',
            'text_content': text_content or '',
            'from_email': request.data.get('from_email', 'noreply@yourcompany.com'),
            'from_name': request.data.get('from_name', 'Your Company'),
            'reply_to': request.data.get('reply_to', 'banuyasin401@gmail.com'),
            'cc_emails': request.data.get('cc_emails', []),
            'bcc_emails': request.data.get('bcc_emails', []),
            'priority': request.data.get('priority', 'normal'),
            'campaign_id': request.data.get('campaign_id', 'simple_email'),
            'tags': request.data.get('tags', ['simple']),
            'template_id': request.data.get('template_id'),
            'template_variables': request.data.get('template_variables', {}),
        }
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        # Send the email using the service
        result = service.send_email(**email_data)
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Email sent successfully',
                'data': {
                    'to_emails': to_emails,
                    'subject': subject,
                    'status': 'sent'
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': 'Failed to send email',
                'error': result.get('error', 'Unknown error')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Reply to an existing email with standard contact information"""
        try:
            # Get the original email
            original_email = self.get_object()
            
            # Get reply content from request
            reply_content = request.data.get('reply_content', '')
            custom_message = request.data.get('custom_message', '')
            
            # Create reply subject
            reply_subject = f"Re: {original_email.subject}"
            if not reply_subject.startswith('Re: '):
                reply_subject = f"Re: {reply_subject}"
            
            # Create standard reply content
            standard_reply_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h3 style="color: #333; margin-top: 0;">Thank you for contacting us!</h3>
                    <p style="color: #666; line-height: 1.6;">
                        We have received your message and appreciate you reaching out to us.
                    </p>
                </div>
                
                {f'<div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px;"><p style="margin: 0; color: #1976d2;"><strong>Your Message:</strong></p><p style="margin: 5px 0 0 0; color: #333;">{reply_content}</p></div>' if reply_content else ''}
                
                {f'<div style="background-color: #f3e5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;"><p style="margin: 0; color: #7b1fa2;"><strong>Our Response:</strong></p><p style="margin: 5px 0 0 0; color: #333;">{custom_message}</p></div>' if custom_message else ''}
                
                <div style="background-color: #fff3e0; padding: 20px; border-radius: 8px; border-left: 4px solid #ff9800;">
                    <h4 style="color: #e65100; margin-top: 0;">Need Further Assistance?</h4>
                    <p style="color: #666; line-height: 1.6; margin-bottom: 15px;">
                        If you have any queries or need additional assistance, please don't hesitate to contact us:
                    </p>
                    <ul style="color: #666; line-height: 1.8; margin: 0; padding-left: 20px;">
                        <li><strong>Email:</strong> support@yourcompany.com</li>
                        <li><strong>Phone:</strong> +1 (555) 123-4567</li>
                        <li><strong>Business Hours:</strong> Monday - Friday, 9:00 AM - 6:00 PM</li>
                        <li><strong>Live Chat:</strong> Available on our website</li>
                    </ul>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated response. Please do not reply to this email directly.
                    </p>
                    <p style="color: #999; font-size: 12px; margin: 5px 0 0 0;">
                        For immediate assistance, please contact us using the information above.
                    </p>
                </div>
            </div>
            """
            
            standard_reply_text = f"""
Thank you for contacting us!

We have received your message and appreciate you reaching out to us.

{f'Your Message: {reply_content}' if reply_content else ''}

{f'Our Response: {custom_message}' if custom_message else ''}

Need Further Assistance?
If you have any queries or need additional assistance, please don't hesitate to contact us:

- Email: support@yourcompany.com
- Phone: +1 (555) 123-4567
- Business Hours: Monday - Friday, 9:00 AM - 6:00 PM
- Live Chat: Available on our website

This is an automated response. Please do not reply to this email directly.
For immediate assistance, please contact us using the information above.

Best regards,
Your Support Team
            """
            
            # Prepare reply email data
            reply_data = {
                'to_emails': original_email.from_email,  # Reply to the original sender
                'subject': reply_subject,
                'html_content': standard_reply_html,
                'text_content': standard_reply_text,
                'from_email': request.data.get('from_email', 'support@yourcompany.com'),
                'from_name': request.data.get('from_name', 'Support Team'),
                'reply_to': request.data.get('reply_to', 'banuyasin401@gmail.com'),
                'priority': request.data.get('priority', 'normal'),
                'campaign_id': f'reply_to_{original_email.id}',
                'tags': ['reply', 'support', 'automated'],
                'template_variables': {
                    'original_subject': original_email.subject,
                    'original_sender': original_email.from_email,
                    'reply_content': reply_content,
                    'custom_message': custom_message
                }
            }
            
            service = EmailOperationsService()
            service.context = {'user': request.user}
            
            # Send the reply email
            result = service.send_email(**reply_data)
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'Reply sent successfully',
                    'data': {
                        'original_email_id': original_email.id,
                        'reply_email_id': result.get('email_id'),
                        'to_emails': original_email.from_email,
                        'subject': reply_subject,
                        'status': 'sent'
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to send reply',
                    'error': result.get('error', 'Unknown error')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except EmailMessage.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Original email not found',
                'error': 'Email with the specified ID does not exist'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Error sending reply',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def send_scheduled(self, request):
        """Schedule an email for future sending"""
        serializer = ScheduledEmailSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        result = service.schedule_email(**serializer.validated_data)
        
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """Resend a failed email"""
        email_message = self.get_object()
        
        if email_message.status not in ['failed', 'bounced']:
            return Response(
                {'error': 'Email can only be resent if it failed or bounced'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        # Reset status and retry
        email_message.status = 'pending'
        email_message.retry_count = 0
        email_message.error_message = None
        email_message.save()
        
        result = service._send_email_message(email_message)
        
        if result['success']:
            return Response({'message': 'Email resent successfully'})
        else:
            return Response(
                {'error': result.get('error', 'Failed to resend email')},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending email"""
        email_message = self.get_object()
        
        if email_message.status not in ['pending', 'sending']:
            return Response(
                {'error': 'Email can only be cancelled if it is pending or sending'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email_message.status = 'cancelled'
        email_message.save()
        
        # Update queue if exists
        try:
            queue_entry = EmailQueue.objects.get(email_message=email_message)
            queue_entry.status = 'cancelled'
            queue_entry.save()
        except EmailQueue.DoesNotExist:
            pass
        
        return Response({'message': 'Email cancelled successfully'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get email statistics"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        campaign_id = request.query_params.get('campaign_id')
        
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        stats = service.get_email_statistics(start_date, end_date, campaign_id)
        
        if 'error' in stats:
            return Response(stats, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def campaign_stats(self, request):
        """Get campaign statistics"""
        campaign_id = request.query_params.get('campaign_id')
        
        if not campaign_id:
            return Response(
                {'error': 'campaign_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get campaign emails
        emails = EmailMessage.objects.filter(
            campaign_id=campaign_id,
            is_deleted=False
        )
        
        # Calculate statistics
        total_emails = emails.count()
        sent_emails = emails.filter(status='sent').count()
        delivered_emails = emails.filter(status='delivered').count()
        
        # Get tracking data
        tracking_events = EmailTracking.objects.filter(
            email_message__in=emails
        )
        
        opened_emails = tracking_events.filter(event_type='opened').values('email_message').distinct().count()
        clicked_emails = tracking_events.filter(event_type='clicked').values('email_message').distinct().count()
        bounced_emails = tracking_events.filter(event_type='bounced').values('email_message').distinct().count()
        complained_emails = tracking_events.filter(event_type='complained').values('email_message').distinct().count()
        unsubscribed_emails = tracking_events.filter(event_type='unsubscribed').values('email_message').distinct().count()
        
        # Calculate rates
        delivery_rate = (delivered_emails / sent_emails * 100) if sent_emails > 0 else 0
        open_rate = (opened_emails / delivered_emails * 100) if delivered_emails > 0 else 0
        click_rate = (clicked_emails / delivered_emails * 100) if delivered_emails > 0 else 0
        bounce_rate = (bounced_emails / sent_emails * 100) if sent_emails > 0 else 0
        complaint_rate = (complained_emails / sent_emails * 100) if sent_emails > 0 else 0
        unsubscribe_rate = (unsubscribed_emails / sent_emails * 100) if sent_emails > 0 else 0
        
        # Get date range
        start_date = emails.aggregate(start=models.Min('created_at'))['start']
        end_date = emails.aggregate(end=models.Max('created_at'))['end']
        
        return Response({
            'campaign_id': campaign_id,
            'campaign_name': campaign_id,  # You might want to get this from a campaign model
            'total_emails': total_emails,
            'sent_emails': sent_emails,
            'delivered_emails': delivered_emails,
            'opened_emails': opened_emails,
            'clicked_emails': clicked_emails,
            'bounced_emails': bounced_emails,
            'complained_emails': complained_emails,
            'unsubscribed_emails': unsubscribed_emails,
            'delivery_rate': round(delivery_rate, 2),
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'complaint_rate': round(complaint_rate, 2),
            'unsubscribe_rate': round(unsubscribe_rate, 2),
            'start_date': start_date,
            'end_date': end_date
        })
    
    @action(detail=False, methods=['get'])
    def sent_emails(self, request):
        """List all sent emails with optional filtering"""
        # Get query parameters for filtering
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        status_filter = request.query_params.get('status', 'sent')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        to_email = request.query_params.get('to_email')
        from_email = request.query_params.get('from_email')
        search = request.query_params.get('search')
        
        # Build queryset for sent emails
        queryset = EmailMessage.objects.filter(
            is_deleted=False,
            status=status_filter
        ).order_by('-sent_at', '-created_at')
        
        # Apply additional filters
        if start_date:
            queryset = queryset.filter(sent_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(sent_at__lte=end_date)
        if to_email:
            queryset = queryset.filter(to_emails__icontains=to_email)
        if from_email:
            queryset = queryset.filter(from_email__icontains=from_email)
        if search:
            queryset = queryset.filter(subject__icontains=search)
        
        # Get total count
        total_count = queryset.count()
        
        # Apply pagination
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        emails = queryset[start_index:end_index]
        
        # Serialize the emails with clean format
        serializer = SentEmailListSerializer(emails, many=True)
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_previous = page > 1
        
        return Response({
            'success': True,
            'data': serializer.data,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_previous': has_previous
            },
            'filters_applied': {
                'status': status_filter,
                'start_date': start_date,
                'end_date': end_date,
                'to_email': to_email,
                'from_email': from_email,
                'search': search
            }
        })


class EmailQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email queue"""
    
    queryset = EmailQueue.objects.all()
    serializer_class = EmailQueueSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queue entries based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by scheduled time
        scheduled_after = self.request.query_params.get('scheduled_after')
        scheduled_before = self.request.query_params.get('scheduled_before')
        
        if scheduled_after:
            queryset = queryset.filter(scheduled_for__gte=scheduled_after)
        if scheduled_before:
            queryset = queryset.filter(scheduled_for__lte=scheduled_before)
        
        return queryset.order_by('scheduled_for', 'priority')
    
    @action(detail=False, methods=['post'])
    def process(self, request):
        """Process pending emails in the queue"""
        service = EmailOperationsService()
        service.context = {'user': request.user}
        
        result = service.process_email_queue()
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed queue entry"""
        queue_entry = self.get_object()
        
        if queue_entry.status != 'failed':
            return Response(
                {'error': 'Only failed queue entries can be retried'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset status and reschedule
        queue_entry.status = 'queued'
        queue_entry.scheduled_for = timezone.now()
        queue_entry.last_error = None
        queue_entry.save()
        
        return Response({'message': 'Queue entry scheduled for retry'})


class EmailTrackingViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email tracking events"""
    
    queryset = EmailTracking.objects.all()
    serializer_class = EmailTrackingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter tracking events based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by email message
        email_message_id = self.request.query_params.get('email_message_id')
        if email_message_id:
            queryset = queryset.filter(email_message_id=email_message_id)
        
        # Filter by event type
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(event_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(event_time__lte=end_date)
        
        return queryset.order_by('-event_time')


class EmailDeliveryReportViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email delivery reports"""
    
    queryset = EmailDeliveryReport.objects.all()
    serializer_class = EmailDeliveryReportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter delivery reports based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by email message
        email_message_id = self.request.query_params.get('email_message_id')
        if email_message_id:
            queryset = queryset.filter(email_message_id=email_message_id)
        
        # Filter by provider
        provider_name = self.request.query_params.get('provider_name')
        if provider_name:
            queryset = queryset.filter(provider_name=provider_name)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(reported_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(reported_at__lte=end_date)
        
        return queryset.order_by('-reported_at')


class EmailAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email analytics"""
    
    queryset = EmailAnalytics.objects.all()
    serializer_class = EmailAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter analytics based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        # Filter by period type
        period_type = self.request.query_params.get('period_type')
        if period_type:
            queryset = queryset.filter(period_type=period_type)
        
        # Filter by campaign
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        # Filter by template
        template_id = self.request.query_params.get('template_id')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        return queryset.order_by('-date')
