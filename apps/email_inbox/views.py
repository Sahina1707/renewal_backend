from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
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
from apps.email_settings.models import EmailAccount
class EmailFolderViewSet(viewsets.ModelViewSet):
    queryset = EmailFolder.objects.filter(is_deleted=False)
    serializer_class = EmailFolderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        folder_type = self.request.query_params.get('folder_type')
        if folder_type:
            queryset = queryset.filter(folder_type=folder_type)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_system = self.request.query_params.get('is_system')
        if is_system is not None:
            queryset = queryset.filter(is_system=is_system.lower() == 'true')
        
        return queryset.order_by('sort_order', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        folder = self.get_object()
        folder.is_active = True
        folder.updated_by = request.user
        folder.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Folder activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        folder = self.get_object()
        folder.is_active = False
        folder.updated_by = request.user
        folder.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Folder deactivated successfully'})
    
    @action(detail=False, methods=['get'])
    def system_folders(self, request):
        folders = self.get_queryset().filter(is_system=True)
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)


class EmailInboxMessageViewSet(viewsets.ModelViewSet):
    queryset = EmailInboxMessage.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmailInboxListSerializer
        elif self.action == 'retrieve':
            return EmailInboxDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return EmailInboxMessageUpdateSerializer
        elif self.action == 'create':
            return EmailInboxMessageCreateSerializer
            
        return EmailInboxDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()

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

        customer_type = self.request.query_params.get('customer_type')
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)

        time_filter = self.request.query_params.get('filter') 
        today = timezone.now().date()
        
        if time_filter == 'today':
            queryset = queryset.filter(received_at__date=today)
        elif time_filter == 'week':
            week_ago = timezone.now() - timezone.timedelta(days=7)
            queryset = queryset.filter(received_at__gte=week_ago)
        elif time_filter == 'month':
            month_ago = timezone.now() - timezone.timedelta(days=30)
            queryset = queryset.filter(received_at__gte=month_ago)

        due_status = self.request.query_params.get('due_status')
        now = timezone.now()
        
        if due_status == 'overdue':
            queryset = queryset.filter(
                due_date__lt=now, 
                status__in=['unread', 'read', 'replied']
            )
        elif due_status == 'due_soon':
            tomorrow = now + timezone.timedelta(days=1)
            queryset = queryset.filter(due_date__gt=now, due_date__lte=tomorrow)
        elif due_status == 'no_due_date':
            queryset = queryset.filter(due_date__isnull=True)

        folder_type = self.request.query_params.get('folder_type')
        folder_id = self.request.query_params.get('folder_id')

        if folder_type == 'trash':
            queryset = EmailInboxMessage.objects.filter(is_deleted=True)
        else:
            queryset = queryset.filter(is_deleted=False)
            
            if folder_type:
                queryset = queryset.filter(folder__folder_type=folder_type)
        
        if folder_id:
            queryset = queryset.filter(folder_id=folder_id)
        
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        is_starred = self.request.query_params.get('is_starred')
        if is_starred is not None:
            queryset = queryset.filter(is_starred=is_starred.lower() == 'true')
        
        is_important = self.request.query_params.get('is_important')
        if is_important is not None:
            queryset = queryset.filter(is_important=is_important.lower() == 'true')
        
        has_attachments = self.request.query_params.get('has_attachments')
        if has_attachments is not None:
            if has_attachments.lower() == 'true':
                queryset = queryset.filter(attachment_count__gt=0)
            else:
                queryset = queryset.filter(attachment_count=0)
        thread_id = self.request.query_params.get('thread_id')
        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)
        
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
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
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
        email_message = self.get_object()
        email_message.is_starred = not email_message.is_starred
        email_message.updated_by = request.user
        email_message.save(update_fields=['is_starred', 'updated_by'])
        
        action = 'starred' if email_message.is_starred else 'unstarred'
        return Response({'message': f'Email {action} successfully'})
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        email_message = self.get_object()
        
        # --- THE FIX: Create folder if it doesn't exist ---
        archive_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='archive',
            defaults={
                'name': 'Archive', 
                'is_system': True,
                'is_active': True
            }
        )
        
        email_message.folder = archive_folder
        email_message.status = 'archived'
        email_message.updated_by = request.user
        
        email_message.save(update_fields=['status', 'folder', 'updated_by'])  
        
        return Response({'message': 'Email moved to Archive successfully'})
    
    @action(detail=False, methods=['post'])
    def send_new(self, request):
        serializer = EmailComposeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
            
        data = serializer.validated_data
        
        sender_account = EmailAccount.objects.filter(user=request.user, is_default_sender=True, is_deleted=False).first()
        if not sender_account:
            sender_account = EmailAccount.objects.filter(user=request.user, is_deleted=False).first()        
        from_email = sender_account.email_address if sender_account else settings.DEFAULT_FROM_EMAIL
       
        
        sent_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='sent', defaults={'name': 'Sent', 'is_system': True}
        )
        
        email_message = EmailInboxMessage.objects.create(
            from_email=from_email,  # <--- Now uses the correct user email
            to_emails=data['to_emails'],
            cc_emails=data.get('cc_emails', []),
            bcc_emails=data.get('bcc_emails', []),
            subject=data['subject'],
            html_content=data.get('html_content', ''),
            text_content=data.get('text_content', ''),
            folder=sent_folder,
            status='read',
            message_id=str(uuid.uuid4()),
            created_by=request.user
        )
        
        service = EmailInboxService()
        success, error = service.send_outbound_email(email_message)
        
        if not success:
            return Response({'error': error}, status=500)
            
        email_message.sent_at = timezone.now()
        email_message.save()
            
        return Response({'message': 'Email sent successfully'}, status=201)
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        email_message = self.get_object()
        email_message.mark_as_read()
        
        return Response({'message': 'Email marked as read'})
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        email_message = self.get_object()
        email_message.status = 'unread'
        email_message.read_at = None
        email_message.updated_by = request.user
        email_message.save(update_fields=['status', 'read_at', 'updated_by'])
        
        return Response({'message': 'Email marked as unread'})
    
    @action(detail=False, methods=['get'])
    def search(self, request):
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
    def dashboard_stats(self, request):
        """
        Returns light summary for the Dashboard Home.
        Includes: Total, Unread, SLA Breaches, Categories (Refund/Complaint etc.)
        """
        service = EmailInboxService()
        data = service.get_dashboard_summary(request.user)
        return Response(data)

    @action(detail=False, methods=['get'])
    def analytics_report(self, request):
        """
        Returns heavy details for the Analytics Page.
        Includes: Agent Performance Table, Campaign Stats, Satisfaction Score.
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        service = EmailInboxService()
        data = service.get_full_analytics_report(start_date, end_date)
        return Response(data)

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        email = self.get_object()
        
        reason = request.data.get('reason')
        priority = request.data.get('priority')
        
        if not reason or not priority:
            return Response(
                {'error': 'Reason and Priority are required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        email.is_escalated = True
        email.escalation_reason = reason
        email.escalation_priority = priority
        email.escalated_at = timezone.now()
        email.escalated_by = request.user
        email.save()
        
        EmailAuditLog.objects.create(
            email_message=email,
            action="Escalated",
            details=f"Priority: {priority} | Reason: {reason}",
            performed_by=request.user
        )

        return Response({'message': 'Email escalated successfully'})

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
        
        EmailAuditLog.objects.create(
            email_message=email,
            action="Category Changed",
            details=f"Changed from {old_category} to {new_category}",
            performed_by=request.user
        )

        return Response({'message': f'Category updated to {new_category}'})
    @action(detail=True, methods=['get'])
    def related_emails(self, request, pk=None):
        current_email = self.get_object()
        
        related = EmailInboxMessage.objects.filter(
            from_email=current_email.from_email,
            is_deleted=False
        ).exclude(id=current_email.id).order_by('-received_at')[:10]
        
        serializer = self.get_serializer(related, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_junk(self, request, pk=None):
        email = self.get_object()
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

    @action(detail=True, methods=['post'])
    def mark_spam(self, request, pk=None):
        email = self.get_object()
        spam_folder = EmailFolder.objects.filter(name__iexact="Spam").first()
        
        if not spam_folder:
             spam_folder, _ = EmailFolder.objects.get_or_create(
                name="Spam", 
                defaults={'folder_type': 'spam', 'is_system': True}
            )
            
        email.folder = spam_folder
        email.is_spam = True
        email.save(update_fields=['folder', 'is_spam'])
        return Response({'message': 'Marked as Spam'})
    @action(detail=True, methods=['post'])
    def mark_spam(self, request, pk=None):
        email = self.get_object()
        
        spam_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='spam', 
            defaults={'name': 'Spam', 'is_system': True}
        )
            
        email.folder = spam_folder
        email.is_spam = True  # Flag it
        email.save(update_fields=['folder', 'is_spam'])
        
        return Response({'message': 'Marked as Spam'})

    @action(detail=True, methods=['post'])
    def unmark_spam(self, request, pk=None):
        email = self.get_object()
        
        inbox_folder = EmailFolder.objects.filter(folder_type='inbox').first()
        if not inbox_folder:
             inbox_folder, _ = EmailFolder.objects.get_or_create(
                name="Inbox", 
                defaults={'folder_type': 'inbox', 'is_system': True}
            )

        email.folder = inbox_folder
        email.is_spam = False       
        email.status = 'read'
        
        email.updated_by = request.user
        email.save(update_fields=['folder', 'is_spam', 'status', 'updated_by'])
        
        return Response({'message': 'Email moved back to Inbox'})

    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        email = self.get_object()
        logs = email.audit_logs.all().order_by('-timestamp')
        serializer = EmailAuditLogSerializer(logs, many=True)
        
        return Response(serializer.data)
    # ... inside class EmailInboxMessageViewSet ...

    @action(detail=False, methods=['post', 'patch'])
    def save_draft(self, request):
        """
        URL: /api/email-inbox/messages/save_draft/
        """
        # 1. Validate Data (Partial allows missing fields like subject)
        serializer = EmailComposeSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        data = serializer.validated_data
        
        # 2. Get 'Drafts' Folder
        draft_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='drafts', 
            defaults={'name': 'Drafts', 'is_system': True}
        )

        # 3. Auto-detect Sender (Same logic as send_new)
        from apps.email_settings.models import EmailAccount
        sender_account = EmailAccount.objects.filter(
            user=request.user, 
            email_address='jhansi07558@gmail.com', # Prioritize your main email
            is_deleted=False
        ).first()
        
        if not sender_account:
            sender_account = EmailAccount.objects.filter(user=request.user, is_default_sender=True).first()
        
        from_email = sender_account.email_address if sender_account else settings.DEFAULT_FROM_EMAIL

        # 4. Create the Draft
        email_message = EmailInboxMessage.objects.create(
            from_email=from_email,
            to_emails=data.get('to_emails', []),
            cc_emails=data.get('cc_emails', []),
            bcc_emails=data.get('bcc_emails', []),
            subject=data.get('subject', '(No Subject)'),
            html_content=data.get('html_content', ''),
            text_content=data.get('text_content', ''),
            folder=draft_folder,      
            status='draft',
            message_id=str(uuid.uuid4()),
            created_by=request.user
        )
        
        return Response({
            'message': 'Draft saved successfully',
            'id': email_message.id,
            'data': self.get_serializer(email_message).data 
        }, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=['post'])
    def send_draft(self, request, pk=None):

        draft = self.get_object()
        
        serializer = EmailComposeSerializer(data=request.data, partial=True)
        
        if serializer.is_valid():
            data = serializer.validated_data
            if 'to_emails' in data: draft.to_emails = data['to_emails']
            if 'cc_emails' in data: draft.cc_emails = data['cc_emails']
            if 'bcc_emails' in data: draft.bcc_emails = data['bcc_emails']
            if 'subject' in data: draft.subject = data['subject']
            if 'html_content' in data: draft.html_content = data['html_content']
            if 'text_content' in data: draft.text_content = data['text_content']
            draft.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        service = EmailInboxService()
        success, error_msg = service.send_outbound_email(draft)

        if success:
            sent_folder, _ = EmailFolder.objects.get_or_create(
                folder_type='sent',
                defaults={'name': 'Sent', 'is_system': True}
            )
            
            draft.folder = sent_folder
            draft.status = 'read'
            draft.sent_at = timezone.now() 
            draft.save()
            
            return Response({'message': 'Draft sent successfully'})
        else:
            return Response({'message': f'Failed to send: {error_msg}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
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
            elif action == 'star' or action == 'flag':
                updated_count = emails.update(is_starred=True, updated_by=request.user)
            elif action == 'unstar' or action == 'unflag':
                updated_count = emails.update(is_starred=False, updated_by=request.user)
            elif action == 'mark_important':
                updated_count = emails.update(is_important=True, updated_by=request.user)
            elif action == 'mark_resolved':
                updated_count = emails.update(status='resolved', updated_by=request.user)
            elif action == 'delete':
                updated_count = emails.update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)
            elif action == 'archive':
                updated_count = emails.update(status='archived', updated_by=request.user)
            
            elif action == 'move_to_folder' and action_value:
                folder = EmailFolder.objects.get(id=action_value)
                updated_count = emails.update(folder=folder, updated_by=request.user)
            
            elif action == 'assign_to' and action_value:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=action_value)
                updated_count = emails.update(assigned_to=user, updated_by=request.user)
                
            elif action == 'add_tag' and action_value:
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
        email_ids = request.data.get('email_ids', [])
        
        if not email_ids:
            return Response({'error': 'No emails selected'}, status=400)

        emails = EmailInboxMessage.objects.filter(id__in=email_ids)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="emails_export.csv"'
        
        writer = csv.writer(response)
        
        writer.writerow([
            'Date Received', 
            'From', 
            'Subject', 
            'Status', 
            'Customer Type', 
            'Priority', 
            'Assigned To'
        ])
        
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
        
        junk_folder, _ = EmailFolder.objects.get_or_create(
            folder_type='junk',
            defaults={'name': 'Junk Email', 'is_system': True}
        )
            
        email.folder = junk_folder
        email.status = 'read'
        email.save(update_fields=['folder', 'status'])
        
        return Response({'message': 'Moved to Junk Email'})

    @action(detail=True, methods=['post'], url_path='add-note')
    def add_note(self, request, pk=None):
        email = self.get_object()
        note_text = request.data.get('note')
        
        if not note_text:
            return Response({'error': 'Note content is required'}, status=status.HTTP_400_BAD_REQUEST)

        note = EmailInternalNote.objects.create(
            email_message=email,
            author=request.user,
            note=note_text
        )
        
        EmailAuditLog.objects.create(
            email_message=email,
            action="Note Added",
            details=f"Note ID: {note.id}",
            performed_by=request.user
        )

        serializer = EmailInternalNoteSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
    queryset = EmailConversation.objects.all()
    serializer_class = EmailConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        thread_id = self.request.query_params.get('thread_id')
        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)
        participant = self.request.query_params.get('participant')
        if participant:
            queryset = queryset.filter(participants__contains=[participant])
        
        return queryset.order_by('-last_message_at')
class EmailFilterViewSet(viewsets.ModelViewSet):
    queryset = EmailFilter.objects.filter(is_deleted=False)
    serializer_class = EmailFilterSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_system = self.request.query_params.get('is_system')
        if is_system is not None:
            queryset = queryset.filter(is_system=is_system.lower() == 'true')
        
        return queryset.order_by('-priority', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        filter_obj = self.get_object()
        filter_obj.is_active = True
        filter_obj.updated_by = request.user
        filter_obj.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Filter activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        filter_obj = self.get_object()
        filter_obj.is_active = False
        filter_obj.updated_by = request.user
        filter_obj.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Filter deactivated successfully'})
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        filter_obj = self.get_object()
        
        recent_emails = EmailInboxMessage.objects.filter(
            is_deleted=False,
            received_at__gte=timezone.now() - timezone.timedelta(days=7)
        )[:100]
        
        matches = []
        for email in recent_emails:
            matches.append({
                'email_id': str(email.id),
                'subject': email.subject,
                'from_email': email.from_email,
                'received_at': email.received_at
            })
        
        return Response({
            'message': f'Filter tested against {len(recent_emails)} recent emails',
            'matches': matches[:10]
        })

    # --- ACTION 1: DYNAMIC SYSTEM RULES LIST ---
    @action(detail=False, methods=['get'])
    def system_rules(self, request):
        """
        Returns ALL rules marked as 'is_system=True' from the database.
        No hardcoded list. If you add a new rule in Postman, it appears here automatically.
        """
        system_filters = EmailFilter.objects.filter(
            is_system=True, 
            is_deleted=False
        ).order_by('-priority')

        response_data = []
        for f in system_filters:
            # Dynamically generate a 'rule_type' key for the frontend
            # Example: "System: Spam Detection" -> "spam_detection"
            # Example: "VIP Auto-Star" -> "vip_auto_star"
            slug_name = f.name.lower().replace("system: ", "").replace(" ", "_").strip()

            response_data.append({
                "id": str(f.id),
                "rule_type": slug_name, # Dynamic key
                "name": f.name.replace("System: ", ""), # Clean display name
                "description": f.description,
                "enabled": f.is_active
            })

        return Response(response_data)

    @action(detail=False, methods=['post'])
    def toggle_rule(self, request):
        """
        Toggles a rule by looking it up in the DB.
        Accepts 'id' (UUID) OR 'rule_type' (Name-based match).
        """
        rule_id = request.data.get('id')
        rule_type = request.data.get('rule_type')
        enabled = request.data.get('enabled')

        filter_obj = None

        if rule_id:
            filter_obj = EmailFilter.objects.filter(id=rule_id, is_system=True).first()
        if not filter_obj and rule_type:
            search_term = rule_type.replace("_", " ")
            filter_obj = EmailFilter.objects.filter(
                name__icontains=search_term, 
                is_system=True
            ).first()

        if not filter_obj:
            return Response(
                {'error': f"Rule not found. Create a system rule matching '{rule_type}' in Postman first."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        filter_obj.is_active = enabled
        filter_obj.updated_by = request.user
        filter_obj.save()

        return Response({
            'status': 'updated', 
            'id': str(filter_obj.id),
            'name': filter_obj.name,
            'active': enabled
        })
class EmailAttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmailAttachment.objects.all()
    serializer_class = EmailAttachmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        email_message_id = self.request.query_params.get('email_message_id')
        if email_message_id:
            queryset = queryset.filter(email_message_id=email_message_id)
        
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type__icontains=content_type)
        
        is_safe = self.request.query_params.get('is_safe')
        if is_safe is not None:
            queryset = queryset.filter(is_safe=is_safe.lower() == 'true')
        
        return queryset.order_by('filename')


class EmailSearchQueryViewSet(viewsets.ModelViewSet):
    queryset = EmailSearchQuery.objects.filter(is_deleted=False)
    serializer_class = EmailSearchQuerySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        is_public = self.request.query_params.get('is_public')
        if is_public is not None:
            queryset = queryset.filter(is_public=is_public.lower() == 'true')
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        created_by = self.request.query_params.get('created_by')
        if created_by:
            queryset = queryset.filter(created_by_id=created_by)
        
        return queryset.order_by('-last_used', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        search_query = self.get_object()
        search_query.increment_usage()
        
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
        
        if not campaign.scheduled_at:
            send_campaign_emails.delay(campaign.id)

    @action(detail=False, methods=['post'])
    def preview(self, request):
        serializer = CampaignPreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
            
        data = serializer.validated_data
        recipient = data.get('sample_recipient', {})
        
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
        
        if data.get('custom_subject'):
            subject = data['custom_subject']
            
        try:
            django_subject = Template(subject)
            django_body = Template(body)
            ctx = Context(recipient)
            final_subject = django_subject.render(ctx)
            final_body = django_body.render(ctx)
            
            if data.get('additional_message'):
                add_msg = data['additional_message']
                final_body = f"<p>{add_msg}</p><hr>{final_body}"
                
            return Response({
                'subject': final_subject,
                'html_content': final_body
            })
            
        except Exception as e:
            return Response({'error': f"Merge error: {str(e)}"}, status=400)
    @action(detail=False, methods=['get'], url_path='export-template')
    def export_template(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="recipient_template.csv"'

        writer = csv.writer(response)
        
        headers = ['email', 'name', 'company', 'policy_number', 'renewal_date', 'premium_amount']
        writer.writerow(headers)
        
        writer.writerow(['example@domain.com', 'John Doe', 'Acme Corp', 'POL-12345', '2025-12-31', '1200.00'])
        
        return response
from rest_framework.permissions import AllowAny

class IncomingEmailWebhookAPIView(APIView):
    """
    The 'Input Door' for real-time emails.
    Triggers AI, Rules, and Threading logic.
    """
    permission_classes = [AllowAny] 

    def post(self, request):
        try:
            data = request.data
            
            # Map the incoming JSON to your service's expected arguments
            service = EmailInboxService()
            result = service.receive_email(
                from_email=data.get('from_email'),
                to_email=data.get('to_email'),
                subject=data.get('subject'),
                html_content=data.get('html_body', ''),
                text_content=data.get('text_body', ''),
                source='webhook'
            )

            if result.get('success'):
                return Response({'status': 'received', 'id': result.get('email_id')}, status=200)
            return Response({'error': result.get('message')}, status=500)

        except Exception as e:
            return Response({'error': str(e)}, status=500)