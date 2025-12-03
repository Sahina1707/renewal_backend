from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
from .tasks import send_campaign_emails,process_scheduled_campaigns
import csv
from django.http import HttpResponse
import uuid
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.template import Template, Context
from .models import (
    EmailInboxMessage, EmailFolder, EmailConversation, EmailFilter,
    EmailAttachment, EmailSearchQuery,EmailInternalNote,
    EmailAuditLog,BulkEmailCampaign)
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
    EmailInboxListSerializer,
    EmailAttachmentSerializer,
    EmailInboxDetailSerializer,
    BulkEmailCampaignSerializer,
    EmailComposeSerializer,
    EmailInternalNoteSerializer,
    EmailAuditLogSerializer,
    EmailConversationSerializer,
    RecipientImportSerializer,
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
        """
        Dynamically select serializer based on the action
        """
        if self.action == 'list':
            return EmailInboxListSerializer
        elif self.action == 'retrieve':
            return EmailInboxDetailSerializer
        return EmailInboxDetailSerializer
    
    def get_queryset(self):
        """Filter email messages based on query parameters"""
        queryset = super().get_queryset()

        # --- 1. Basic Filters (Apply once) ---
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        sentiment = self.request.query_params.get('sentiment')
        if sentiment:
            queryset = queryset.filter(sentiment=sentiment)

        # --- 2. Folder Logic (Consolidated) ---
        folder_type = self.request.query_params.get('folder_type')
        folder_id = self.request.query_params.get('folder_id')

        # Handle Trash vs Normal Folders
        if folder_type == 'trash':
            # Specific case: Show deleted items
            queryset = EmailInboxMessage.objects.filter(is_deleted=True)
        else:
            # Default: Hide deleted items
            queryset = EmailInboxMessage.objects.filter(is_deleted=False)
            # Apply folder type filter if not trash
            if folder_type:
                queryset = queryset.filter(folder__folder_type=folder_type)

        if folder_id:
            queryset = queryset.filter(folder_id=folder_id)
        
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        thread_id = self.request.query_params.get('thread_id')
        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)

        is_starred = self.request.query_params.get('is_starred')
        if is_starred is not None:
            queryset = queryset.filter(is_starred=is_starred.lower() == 'true')
        
        is_important = self.request.query_params.get('is_important')
        if is_important is not None:
            queryset = queryset.filter(is_important=is_important.lower() == 'true')
        
        # --- 6. Attachment Filter ---
        has_attachments = self.request.query_params.get('has_attachments')
        if has_attachments is not None:
            if has_attachments.lower() == 'true':
                queryset = queryset.filter(attachments__isnull=False).distinct()
            else:
                queryset = queryset.filter(attachments__isnull=True)
        
        # --- 7. Date Range ---
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(received_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(received_at__lte=end_date)
        
        # --- 8. Text Search ---
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
        """Archive an email (FIXED: Removed duplicate logic)"""
        email_message = self.get_object()
        
        archive_folder = EmailFolder.objects.filter(folder_type='archive').first()
        if archive_folder:
            email_message.folder = archive_folder
        
        email_message.status = 'archived'
        email_message.updated_by = request.user
        
        # Saves folder and status update once
        email_message.save(update_fields=['status', 'folder', 'updated_by'])  
        
        return Response({'message': 'Email moved to Archive successfully'})
    
    @action(detail=False, methods=['post'])
    def send_new(self, request):
        """
        Endpoint to Compose & Send a brand new email. (FIXED: Added created_by)
        """
        # ... (Serializer validation remains the same) ...
        
        email_message = EmailInboxMessage(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=data['to_emails'],
            # ... (other fields) ...
            folder=sent_folder, 
            status='read', 
            message_id=new_uuid,
            thread_id=new_uuid,
            created_by=request.user 
        )
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
    @action(detail=True, methods=['get'])
    def related_emails(self, request, pk=None):
        """Finds other emails from the same sender"""
        current_email = self.get_object()
        
        # Find emails with the same sender, excluding the current one
        related = EmailInboxMessage.objects.filter(
            from_email=current_email.from_email,
            is_deleted=False
        ).exclude(id=current_email.id).order_by('-received_at')[:10]  # Limit to 10
        
        serializer = self.get_serializer(related, many=True)
        return Response(serializer.data)

    # --- Feature: Mark as Junk (Matches Image Menu) ---
    @action(detail=True, methods=['post'])
    def mark_junk(self, request, pk=None):
        email = self.get_object()
        # Find the 'Junk Email' folder (type='spam' usually, or custom)
        junk_folder = EmailFolder.objects.filter(name__icontains="Junk").first()
        
        # Fallback if not found
        if not junk_folder:
             junk_folder, _ = EmailFolder.objects.get_or_create(
                name="Junk Email", 
                defaults={'folder_type': 'spam', 'is_system': True}
            )
            
        email.folder = junk_folder
        email.save(update_fields=['folder'])
        return Response({'message': 'Moved to Junk Email'})

    # --- Feature: Mark as Spam (Matches Image Menu) ---
    @action(detail=True, methods=['post'])
    def mark_spam(self, request, pk=None):
        email = self.get_object()
        # Find the 'Spam' folder
        spam_folder = EmailFolder.objects.filter(name__iexact="Spam").first()
        
        if not spam_folder:
             spam_folder, _ = EmailFolder.objects.get_or_create(
                name="Spam", 
                defaults={'folder_type': 'spam', 'is_system': True}
            )
            
        email.folder = spam_folder
        email.is_spam = True  # Also flag the boolean
        email.save(update_fields=['folder', 'is_spam'])
        return Response({'message': 'Marked as Spam'})
    # In views.py -> EmailInboxMessageViewSet

    @action(detail=True, methods=['post'])
    def unmark_spam(self, request, pk=None):
        """
        Moves an email from Spam back to Inbox (Not Junk).
        URL: POST /api/email-inbox/messages/{id}/unmark_spam/
        """
        email = self.get_object()
        
        # 1. Find the System Inbox Folder
        inbox_folder = EmailFolder.objects.filter(folder_type='inbox').first()
        if not inbox_folder:
             # Fallback just in case
             inbox_folder, _ = EmailFolder.objects.get_or_create(
                name="Inbox", 
                defaults={'folder_type': 'inbox', 'is_system': True}
            )

        # 2. Update the Email
        email.folder = inbox_folder
        email.is_spam = False       
        email.status = 'read'
        
        email.updated_by = request.user
        email.save(update_fields=['folder', 'is_spam', 'status', 'updated_by'])
        
        return Response({'message': 'Email moved back to Inbox'})

    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        """
        Returns the history of actions performed on this email.
        """
        email = self.get_object()
        logs = email.audit_logs.all().order_by('-timestamp')
        serializer = EmailAuditLogSerializer(logs, many=True)
        
        return Response(serializer.data)
    @action(detail=True, methods=['post'])
    def send_draft(self, request, pk=None):

        draft = self.get_object()
        
        serializer = EmailComposeSerializer(data=request.data, partial=True)
        
        if serializer.is_valid():
            data = serializer.validated_data
            # Update fields only if they are provided in the request
            if 'to_emails' in data: draft.to_emails = data['to_emails']
            if 'cc_emails' in data: draft.cc_emails = data['cc_emails']
            if 'bcc_emails' in data: draft.bcc_emails = data['bcc_emails']
            if 'subject' in data: draft.subject = data['subject']
            if 'html_content' in data: draft.html_content = data['html_content']
            if 'text_content' in data: draft.text_content = data['text_content']
            draft.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 2. Send the email using the existing Service
        service = EmailInboxService()
        # Note: send_outbound_email is defined in your services.py
        success, error_msg = service.send_outbound_email(draft)

        if success:
            # 3. If sent successfully, move it to the 'Sent' folder
            sent_folder, _ = EmailFolder.objects.get_or_create(
                folder_type='sent',
                defaults={'name': 'Sent', 'is_system': True}
            )
            
            draft.folder = sent_folder
            draft.status = 'read'  # Outgoing emails are considered 'read'
            draft.sent_at = timezone.now() 
            draft.save()
            
            return Response({'message': 'Draft sent successfully'})
        else:
            return Response({'message': f'Failed to send: {error_msg}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """
        Unified Bulk Action Endpoint
        """
        serializer = BulkEmailActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email_ids = serializer.validated_data['email_ids']
        action = serializer.validated_data['action']
        action_value = serializer.validated_data.get('action_value')
        
        emails = EmailInboxMessage.objects.filter(id__in=email_ids)
        updated_count = 0
        
        try:
            if action == 'mark_read':
                updated_count = emails.update(status='read', read_at=timezone.now(), updated_by=request.user)
            elif action == 'mark_unread':
                updated_count = emails.update(status='unread', read_at=None, updated_by=request.user)
            elif action == 'star' or action == 'flag': # Handle both names
                updated_count = emails.update(is_starred=True, updated_by=request.user)
            elif action == 'unstar' or action == 'unflag':
                updated_count = emails.update(is_starred=False, updated_by=request.user)
            elif action == 'mark_important':
                updated_count = emails.update(is_important=True, updated_by=request.user)
            elif action == 'mark_resolved':
                updated_count = emails.update(status='resolved', updated_by=request.user)
            elif action == 'delete':
                # Soft delete individually to trigger signals if needed, or use bulk update for speed
                updated_count = emails.update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)
            elif action == 'archive':
                updated_count = emails.update(status='archived', updated_by=request.user)
            
            # Actions requiring values
            elif action == 'move_to_folder' and action_value:
                folder = EmailFolder.objects.get(id=action_value)
                updated_count = emails.update(folder=folder, updated_by=request.user)
            
            elif action == 'assign_to' and action_value:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=action_value)
                updated_count = emails.update(assigned_to=user, updated_by=request.user)
                
            elif action == 'add_tag' and action_value:
                # JSONField appending is database specific, looping is safer for generic DBs
                for email in emails:
                    if action_value not in email.tags:
                        email.tags.append(action_value)
                        email.save()
                        updated_count += 1
                        
            elif action == 'remove_tag' and action_value:
                for email in emails:
                    if action_value in email.tags:
                        email.tags.remove(action_value)
                        email.save()
                        updated_count += 1

            return Response({
                'message': f'Bulk action {action} completed.',
                'updated_count': updated_count
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)
    @action(detail=False, methods=['post'])
    def export_selected(self, request):
        """
        API for "Export Selected" button. Returns a CSV file.
        URL: POST /api/email-inbox/messages/export_selected/
        """
        email_ids = request.data.get('email_ids', [])
        
        if not email_ids:
            return Response({'error': 'No emails selected'}, status=400)

        emails = EmailInboxMessage.objects.filter(id__in=email_ids)
        
        # Create the CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="emails_export.csv"'
        
        writer = csv.writer(response)
        
        # 1. Write Header Row
        writer.writerow([
            'Date Received', 
            'From', 
            'Subject', 
            'Status', 
            'Customer Type', 
            'Priority', 
            'Assigned To'
        ])
        
        # 2. Write Data Rows
        for email in emails:
            writer.writerow([
                email.received_at.strftime("%Y-%m-%d %H:%M") if email.received_at else "",
                email.from_email,
                email.subject,
                email.get_status_display(),
                email.customer_type,  # From your new field
                email.priority,
                email.assigned_to.get_full_name() if email.assigned_to else "Unassigned"
            ])
            
        return response
    @action(detail=True, methods=['post'])
    def mark_junk(self, request, pk=None):
        email = self.get_object()
        
        # Find or Create 'Junk' folder
        junk_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='junk',  # <--- Uses the new type
            defaults={'name': 'Junk Email', 'is_system': True}
        )
            
        email.folder = junk_folder
        email.status = 'read' # Optional: mark as read when moving to junk
        email.save(update_fields=['folder', 'status'])
        
        return Response({'message': 'Moved to Junk Email'})

    # --- ACTION 2: MARK AS SPAM (Red Folder) ---
    @action(detail=True, methods=['post'])
    def mark_spam(self, request, pk=None):
        email = self.get_object()
        
        # Find or Create 'Spam' folder
        spam_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='spam', 
            defaults={'name': 'Spam', 'is_system': True}
        )
            
        email.folder = spam_folder
        email.is_spam = True  
        email.save(update_fields=['folder', 'is_spam'])
        
        return Response({'message': 'Marked as Spam'})
    @action(detail=True, methods=['post'], url_path='add-note') # explicit url_path handles hyphens
    def add_note(self, request, pk=None):
        """
        Adds an internal note to the specific email message.
        """
        email = self.get_object()
        note_text = request.data.get('note')
        
        if not note_text:
            return Response({'error': 'Note content is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the note linked to this specific email
        note = EmailInternalNote.objects.create(
            email_message=email,
            author=request.user,
            note=note_text
        )
        
        # Log to Audit Trail
        EmailAuditLog.objects.create(
            email_message=email,
            action="Note Added",
            details=f"Note ID: {note.id}",
            performed_by=request.user
        )

        serializer = EmailInternalNoteSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # --- FIX 2: ADD MISSING TAG ENDPOINTS ---
    @action(detail=True, methods=['post'])
    def add_tag(self, request, pk=None):
        email = self.get_object()
        tag = request.data.get('tag')
        
        if not tag:
            return Response({'error': 'Tag is required'}, status=400)
            
        if tag not in email.tags:
            email.tags.append(tag)
            email.save(update_fields=['tags'])
            
        return Response({'message': 'Tag added', 'tags': email.tags})

    @action(detail=True, methods=['post'])
    def remove_tag(self, request, pk=None):
        email = self.get_object()
        tag = request.data.get('tag')
        
        if tag in email.tags:
            email.tags.remove(tag)
            email.save(update_fields=['tags'])
            
        return Response({'message': 'Tag removed', 'tags': email.tags})

    # --- FIX 3: ADD MISSING MOVE FOLDER ENDPOINT ---
    @action(detail=True, methods=['post'])
    def move_to_folder(self, request, pk=None):
        email = self.get_object()
        folder_id = request.data.get('folder_id')
        
        if not folder_id:
             return Response({'error': 'folder_id is required'}, status=400)
             
        try:
            folder = EmailFolder.objects.get(id=folder_id)
            email.folder = folder
            email.save(update_fields=['folder'])
            return Response({'message': f'Moved to {folder.name}'})
        except EmailFolder.DoesNotExist:
            return Response({'error': 'Folder not found'}, status=404)

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

    @action(detail=False, methods=['post'])
    def save_draft(self, request):
        """
        Saves an email as a draft without sending it.
        """
        serializer = EmailComposeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        data = serializer.validated_data
        import uuid

        # Find or create the 'drafts' folder
        draft_folder = EmailFolder.objects.filter(folder_type='drafts').first()
        if not draft_folder:
             # Fallback if folder doesn't exist yet
            draft_folder = EmailFolder.objects.create(name="Drafts", folder_type="drafts", is_system=True)

        email_message = EmailInboxMessage.objects.create(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=data['to_emails'],
            cc_emails=data['cc_emails'],
            bcc_emails=data['bcc_emails'],
            subject=data['subject'],
            html_content=data.get('html_content', ''),
            text_content=data.get('text_content', ''),
            folder=draft_folder,      
            status='draft',           
            message_id=str(uuid.uuid4()),
            created_by=request.user
        )

        return Response({
            'message': 'Draft saved successfully',
            'id': email_message.id
        }, status=status.HTTP_201_CREATED)


# In views.py

class EmailFilterViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email filters, including system and custom rules."""
    
    # CRITICAL FIX: Explicitly define queryset for DRF/Celery initialization
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
        
        # NOTE: Full filter matching logic should ideally be called from EmailInboxService here.
        matches = []
        for email in recent_emails:
            # Placeholder for actual matching logic
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

    @action(detail=False, methods=['post'])
    def toggle_rule(self, request):
        """
        API to toggle system rules like 'VIP Customer Auto-Star' and 'Spam Detection'.
        URL: POST /api/email-inbox/filters/toggle_rule/
        Payload: { "rule_type": "vip_auto_star", "enabled": true }
        """
        rule_type = request.data.get('rule_type')
        enabled = request.data.get('enabled')
        
        # Map specific UI toggles to actual Filter definitions
        if rule_type == 'vip_auto_star':
            filter_obj, _ = EmailFilter.objects.get_or_create(
                name="System: VIP Auto-Star",
                defaults={
                    'filter_type': 'body',
                    'operator': 'contains',
                    'value': 'VIP',
                    'action': 'mark_as_important',
                    'is_system': True,
                    'priority': 100 # High priority for system rules
                }
            )
            filter_obj.is_active = enabled
            filter_obj.save()
            return Response({'status': 'updated', 'rule': rule_type, 'active': enabled})

        elif rule_type == 'spam_detection':
            filter_obj, _ = EmailFilter.objects.get_or_create(
                name="System: Spam Detection",
                defaults={
                    'filter_type': 'subject', 
                    'operator': 'contains',
                    'value': 'SPAM',
                    'action': 'move_to_folder',
                    'action_value': EmailFolder.objects.filter(folder_type='spam').first().id if EmailFolder.objects.filter(folder_type='spam').exists() else None,
                    'is_system': True
                }
            )
            filter_obj.is_active = enabled
            filter_obj.save()
            return Response({'status': 'updated', 'rule': rule_type, 'active': enabled})
            
        return Response({'error': 'Unknown rule type'}, status=400)
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
class BulkEmailCampaignViewSet(viewsets.ModelViewSet):
    queryset = BulkEmailCampaign.objects.all()
    serializer_class = BulkEmailCampaignSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        campaign = serializer.save(created_by=self.request.user)
        
        # If scheduled immediately (or null), trigger standard processing
        # If scheduled for later, the Celery Beat task will pick it up
        if not campaign.scheduled_at:
            send_campaign_emails.delay(campaign.id)

    @action(detail=False, methods=['post'])
    def preview(self, request):
        """
        Generates a preview for Step 4 of the wizard.
        Merges the template + custom message + recipient data.
        """
        serializer = CampaignPreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
            
        data = serializer.validated_data
        recipient = data.get('sample_recipient', {})
        
        # 1. Get Base Content
        subject = ""
        body = ""
        
        if data.get('template_id'):
            try:
                EmailTemplate = apps.get_model('email_templates', 'EmailTemplate')
                template = EmailTemplate.objects.get(id=data['template_id'])
                subject = template.subject
                body = getattr(template, 'body_html', getattr(template, 'html_content', ''))
            except:
                return Response({'error': 'Template not found'}, status=404)
        
        # 2. Apply Custom Overrides (Step 2 inputs)
        if data.get('custom_subject'):
            subject = data['custom_subject']
            
        try:
            django_subject = Template(subject)
            django_body = Template(body)
            ctx = Context(recipient)
            final_subject = django_subject.render(ctx)
            final_body = django_body.render(ctx)
            
            # 4. Inject Additional Message if present
            if data.get('additional_message'):
                add_msg = data['additional_message']
                # Simple injection: Append to top of body
                final_body = f"<p>{add_msg}</p><hr>{final_body}"
                
            return Response({
                'subject': final_subject,
                'html_content': final_body
            })
            
        except Exception as e:
            return Response({'error': f"Merge error: {str(e)}"}, status=400)
    @action(detail=False, methods=['get'], url_path='export-template')
    def export_template(self, request):
        """
        Generates a CSV template for the 'Export Template' button in the UI.
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="recipient_template.csv"'

        writer = csv.writer(response)
        
        # Matches the fields expected by your Import Logic
        headers = ['email', 'name', 'company', 'policy_number', 'renewal_date', 'premium_amount']
        writer.writerow(headers)
        
        # Add a sample row so users know what to type
        writer.writerow(['example@domain.com', 'John Doe', 'Acme Corp', 'POL-12345', '2025-12-31', '1200.00'])
        
        return response
