from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings

from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery
)
from .serializers import (EmailInboxMessageSerializer, 
    EmailInboxMessageCreateSerializer, 
    EmailInboxMessageUpdateSerializer,
    EmailFolderSerializer, 
    EmailConversationSerializer, 
    EmailFilterSerializer,
    EmailAttachmentSerializer, 
    EmailSearchQuerySerializer, 
    EmailReplySerializer,
    EmailForwardSerializer, 
    BulkEmailActionSerializer, 
    EmailSearchSerializer,
    EmailStatisticsSerializer,
    EmailComposeSerializer
)
from .services import EmailInboxService


class EmailFolderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email folders"""
    
    queryset = EmailFolder.objects.filter(is_deleted=False)
    serializer_class = EmailFolderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter folders based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by folder type
        folder_type = self.request.query_params.get('folder_type')
        if folder_type:
            queryset = queryset.filter(folder_type=folder_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by system folders
        is_system = self.request.query_params.get('is_system')
        if is_system is not None:
            queryset = queryset.filter(is_system=is_system.lower() == 'true')
        
        return queryset.order_by('sort_order', 'name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new folder"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating a folder"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the folder"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a folder"""
        folder = self.get_object()
        folder.is_active = True
        folder.updated_by = request.user
        folder.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Folder activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a folder"""
        folder = self.get_object()
        folder.is_active = False
        folder.updated_by = request.user
        folder.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Folder deactivated successfully'})
    
    @action(detail=False, methods=['get'])
    def system_folders(self, request):
        """Get system folders"""
        folders = self.get_queryset().filter(is_system=True)
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)


class EmailInboxMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email inbox messages"""
    
    queryset = EmailInboxMessage.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EmailInboxMessageCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EmailInboxMessageUpdateSerializer
        return EmailInboxMessageSerializer
    
    def get_queryset(self):
        """Filter email messages based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by sentiment
        sentiment = self.request.query_params.get('sentiment')
        if sentiment:
            queryset = queryset.filter(sentiment=sentiment)
        
        # Filter by folder
        folder_id = self.request.query_params.get('folder_id')
        if folder_id:
            queryset = queryset.filter(folder_id=folder_id)
        
        # Filter by assigned user
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)
        
        # Filter by starred status
        is_starred = self.request.query_params.get('is_starred')
        if is_starred is not None:
            queryset = queryset.filter(is_starred=is_starred.lower() == 'true')
        
        # Filter by important status
        is_important = self.request.query_params.get('is_important')
        if is_important is not None:
            queryset = queryset.filter(is_important=is_important.lower() == 'true')
        
        # Filter by has attachments
        has_attachments = self.request.query_params.get('has_attachments')
        if has_attachments is not None:
            if has_attachments.lower() == 'true':
                queryset = queryset.filter(attachments__isnull=False).distinct()
            else:
                queryset = queryset.filter(attachments__isnull=True)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(received_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(received_at__lte=end_date)
        
        # Search by subject, from, or content
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search) |
                Q(from_email__icontains=search) |
                Q(text_content__icontains=search) |
                Q(html_content__icontains=search)
            )
        
        return queryset.order_by('-received_at')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new email message"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating an email message"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the email message"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Reply to an email"""
        email_message = self.get_object()
        serializer = EmailReplySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = EmailInboxService()
        result = service.reply_to_email(
            email_id=str(email_message.id),
            **serializer.validated_data
        )
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def forward(self, request, pk=None):
        """Forward an email"""
        email_message = self.get_object()
        serializer = EmailForwardSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = EmailInboxService()
        result = service.forward_email(
            email_id=str(email_message.id),
            **serializer.validated_data
        )
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def star(self, request, pk=None):
        """Star/unstar an email"""
        email_message = self.get_object()
        email_message.is_starred = not email_message.is_starred
        email_message.updated_by = request.user
        email_message.save(update_fields=['is_starred', 'updated_by'])
        
        action = 'starred' if email_message.is_starred else 'unstarred'
        return Response({'message': f'Email {action} successfully'})
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive an email"""
        email_message = self.get_object()
        email_message.status = 'archived'
        email_message.updated_by = request.user
        email_message.save(update_fields=['status', 'updated_by'])
        
        return Response({'message': 'Email archived successfully'})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark email as read"""
        email_message = self.get_object()
        email_message.mark_as_read()
        
        return Response({'message': 'Email marked as read'})
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        """Mark email as unread"""
        email_message = self.get_object()
        email_message.status = 'unread'
        email_message.read_at = None
        email_message.updated_by = request.user
        email_message.save(update_fields=['status', 'read_at', 'updated_by'])
        
        return Response({'message': 'Email marked as unread'})
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk action on multiple emails"""
        serializer = BulkEmailActionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email_ids = serializer.validated_data['email_ids']
        action = serializer.validated_data['action']
        action_value = serializer.validated_data.get('action_value')
        
        emails = EmailInboxMessage.objects.filter(id__in=email_ids, is_deleted=False)
        updated_count = 0
        
        for email in emails:
            try:
                if action == 'mark_read':
                    email.mark_as_read()
                elif action == 'mark_unread':
                    email.status = 'unread'
                    email.read_at = None
                elif action == 'star':
                    email.is_starred = True
                elif action == 'unstar':
                    email.is_starred = False
                elif action == 'mark_important':
                    email.is_important = True
                elif action == 'unmark_important':
                    email.is_important = False
                elif action == 'move_to_folder':
                    if action_value:
                        folder = EmailFolder.objects.get(id=action_value)
                        email.folder = folder
                elif action == 'delete':
                    email.soft_delete()
                elif action == 'archive':
                    email.status = 'archived'
                elif action == 'assign_to':
                    if action_value:
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        user = User.objects.get(id=action_value)
                        email.assigned_to = user
                elif action == 'add_tag':
                    if action_value and action_value not in email.tags:
                        email.tags.append(action_value)
                elif action == 'remove_tag':
                    if action_value and action_value in email.tags:
                        email.tags.remove(action_value)
                
                email.updated_by = request.user
                email.save()
                updated_count += 1
                
            except Exception as e:
                continue
        
        return Response({
            'message': f'Bulk action completed. {updated_count} emails updated.',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced search for emails"""
        serializer = EmailSearchSerializer(data=request.query_params)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = EmailInboxService()
        result = service.search_emails(serializer.validated_data)
        
        if result['success']:
            email_serializer = self.get_serializer(result['emails'], many=True)
            return Response({
                'emails': email_serializer.data,
                'total_count': result['total_count'],
                'page': result['page'],
                'page_size': result['page_size'],
                'total_pages': result['total_pages']
            })
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get email statistics"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        service = EmailInboxService()
        stats = service.get_email_statistics(start_date, end_date)
        
        if 'error' in stats:
            return Response(stats, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(stats)
    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        email = self.get_object()
        
        # 1. Get data from the Modal
        reason = request.data.get('reason')
        priority = request.data.get('priority')
        
        if not reason or not priority:
            return Response(
                {'error': 'Reason and Priority are required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Update the Email
        email.is_escalated = True
        email.escalation_reason = reason
        email.escalation_priority = priority
        email.escalated_at = timezone.now()
        email.escalated_by = request.user
        email.save()
        
        # 3. Log to Audit Trail
        EmailAuditLog.objects.create(
            email_message=email,
            action="Escalated",
            details=f"Priority: {priority} | Reason: {reason}",
            performed_by=request.user
        )

        return Response({'message': 'Email escalated successfully'})

    # --- Feature: Set Customer Category (Matches Image 1 Menu) ---
    @action(detail=True, methods=['post'])
    def set_category(self, request, pk=None):
        email = self.get_object()
        new_category = request.data.get('category')
        
        valid_choices = dict(EmailInboxMessage.CUSTOMER_TYPE_CHOICES).keys()
        if new_category not in valid_choices:
            return Response({'error': 'Invalid category'}, status=status.HTTP_400_BAD_REQUEST)

        old_category = email.customer_type
        email.customer_type = new_category
        email.save()
        
        # Log to Audit Trail
        EmailAuditLog.objects.create(
            email_message=email,
            action="Category Changed",
            details=f"Changed from {old_category} to {new_category}",
            performed_by=request.user
        )

        return Response({'message': f'Category updated to {new_category}'})

    # --- Feature: View Audit Trail (Matches Image 1 Menu) ---
    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        email = self.get_object()
        logs = email.audit_logs.all()
        
        # Simple inline serialization for the logs
        data = [{
            'action': log.action,
            'details': log.details,
            'performed_by': log.performed_by.get_full_name() if log.performed_by else 'System',
            'timestamp': log.timestamp
        } for log in logs]
        
        return Response(data)
    @action(detail=False, methods=['post'])
    def send_new(self, request):
        """
        Endpoint to Compose & Send a brand new email.
        URL: POST /api/email-inbox/messages/send_new/
        """
        serializer = EmailComposeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        data = serializer.validated_data
        
        # 1. Create the Email Object in DB (Folder = Sent)
        import uuid
        email_message = EmailInboxMessage.objects.create(
            from_email=settings.DEFAULT_FROM_EMAIL, # Your system email
            to_emails=data['to_emails'],
            cc_emails=data['cc_emails'],
            bcc_emails=data['bcc_emails'],
            subject=data['subject'],
            html_content=data.get('html_content', ''),
            text_content=data.get('text_content', ''),
            folder=EmailFolder.objects.filter(folder_type='sent').first(), # Save to 'Sent' folder
            status='read', # Outgoing emails are read by definition
            message_id=str(uuid.uuid4()),
            created_by=request.user
        )

        # 2. Actually Send it via SMTP
        service = EmailInboxService()
        success, error_msg = service.send_outbound_email(email_message)

        if success:
            return Response({
                'message': 'Email sent successfully',
                'id': email_message.id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'message': f'Failed to send: {error_msg}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmailConversationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email conversations"""
    
    queryset = EmailConversation.objects.all()
    serializer_class = EmailConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter conversations based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by thread ID
        thread_id = self.request.query_params.get('thread_id')
        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)
        
        # Filter by participant
        participant = self.request.query_params.get('participant')
        if participant:
            queryset = queryset.filter(participants__contains=[participant])
        
        return queryset.order_by('-last_message_at')


class EmailFilterViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email filters"""
    
    queryset = EmailFilter.objects.filter(is_deleted=False)
    serializer_class = EmailFilterSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter filters based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by system filters
        is_system = self.request.query_params.get('is_system')
        if is_system is not None:
            queryset = queryset.filter(is_system=is_system.lower() == 'true')
        
        return queryset.order_by('-priority', 'name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new filter"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating a filter"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the filter"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a filter"""
        filter_obj = self.get_object()
        filter_obj.is_active = True
        filter_obj.updated_by = request.user
        filter_obj.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Filter activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a filter"""
        filter_obj = self.get_object()
        filter_obj.is_active = False
        filter_obj.updated_by = request.user
        filter_obj.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Filter deactivated successfully'})
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test a filter against recent emails"""
        filter_obj = self.get_object()
        
        # Get recent emails to test against
        recent_emails = EmailInboxMessage.objects.filter(
            is_deleted=False,
            received_at__gte=timezone.now() - timezone.timedelta(days=7)
        )[:100]
        
        matches = []
        for email in recent_emails:
            # This would use the same logic as in the service
            # For now, just return a simple response
            matches.append({
                'email_id': str(email.id),
                'subject': email.subject,
                'from_email': email.from_email,
                'received_at': email.received_at
            })
        
        return Response({
            'message': f'Filter tested against {len(recent_emails)} recent emails',
            'matches': matches[:10]  # Return first 10 matches
        })


class EmailAttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email attachments"""
    
    queryset = EmailAttachment.objects.all()
    serializer_class = EmailAttachmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter attachments based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by email message
        email_message_id = self.request.query_params.get('email_message_id')
        if email_message_id:
            queryset = queryset.filter(email_message_id=email_message_id)
        
        # Filter by file type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type__icontains=content_type)
        
        # Filter by safety status
        is_safe = self.request.query_params.get('is_safe')
        if is_safe is not None:
            queryset = queryset.filter(is_safe=is_safe.lower() == 'true')
        
        return queryset.order_by('filename')


class EmailSearchQueryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email search queries"""
    
    queryset = EmailSearchQuery.objects.filter(is_deleted=False)
    serializer_class = EmailSearchQuerySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter search queries based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by public/private
        is_public = self.request.query_params.get('is_public')
        if is_public is not None:
            queryset = queryset.filter(is_public=is_public.lower() == 'true')
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by created by
        created_by = self.request.query_params.get('created_by')
        if created_by:
            queryset = queryset.filter(created_by_id=created_by)
        
        return queryset.order_by('-last_used', 'name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new search query"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating a search query"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the search query"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a saved search query"""
        search_query = self.get_object()
        search_query.increment_usage()
        
        # Execute the search using the saved parameters
        service = EmailInboxService()
        result = service.search_emails(search_query.query_params)
        
        if result['success']:
            email_serializer = EmailInboxMessageSerializer(result['emails'], many=True)
            return Response({
                'emails': email_serializer.data,
                'total_count': result['total_count'],
                'page': result['page'],
                'page_size': result['page_size'],
                'total_pages': result['total_pages']
            })
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
