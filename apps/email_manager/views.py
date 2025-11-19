from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import EmailManager, EmailReply, StartedReplyMail
from .serializers import (
    EmailManagerSerializer,
    EmailManagerCreateSerializer,
    EmailManagerUpdateSerializer,
    SentEmailListSerializer,
    EmailReplySerializer
)
from .services import EmailManagerService
from apps.templates.models import Template
from apps.customer_payment_schedule.models import PaymentSchedule
from rest_framework.views import APIView
from .models import EmailManagerInbox
from .serializers import EmailManagerInboxSerializer
from .services import EmailInboxService
from .ai_utils import analyze_email_sentiment_and_intent
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from .ai_utils import analyze_email_sentiment_and_intent
from django.template import Template as DjangoTemplate, Context

class EmailManagerViewSet(viewsets.ModelViewSet):
    
    queryset = EmailManager.objects.all()
    serializer_class = EmailManagerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EmailManagerCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EmailManagerUpdateSerializer
        return EmailManagerSerializer
    
    def get_queryset(self):
        queryset = EmailManager.objects.filter(is_deleted=False)
        
        email = self.request.query_params.get('email', None)
        if email:
            queryset = queryset.filter(
                Q(to__icontains=email) |
                Q(cc__icontains=email) |
                Q(bcc__icontains=email)
            )
        
        policy_number = self.request.query_params.get('policy_number', None)
        if policy_number:
            queryset = queryset.filter(policy_number__icontains=policy_number)
        
        customer_name = self.request.query_params.get('customer_name', None)
        if customer_name:
            queryset = queryset.filter(customer_name__icontains=customer_name)
        
        priority = self.request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)
        
        schedule_send = self.request.query_params.get('schedule_send', None)
        if schedule_send is not None:
            schedule_send_bool = schedule_send.lower() == 'true'
            queryset = queryset.filter(schedule_send=schedule_send_bool)
        
        email_status = self.request.query_params.get('email_status', None)
        if email_status:
            queryset = queryset.filter(email_status=email_status)
        
        track_opens = self.request.query_params.get('track_opens', None)
        if track_opens is not None:
            track_opens_bool = track_opens.lower() == 'true'
            queryset = queryset.filter(track_opens=track_opens_bool)
        
        track_clicks = self.request.query_params.get('track_clicks', None)
        if track_clicks is not None:
            track_clicks_bool = track_clicks.lower() == 'true'
            queryset = queryset.filter(track_clicks=track_clicks_bool)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search) |
                Q(message__icontains=search) |
                Q(customer_name__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        template_id = data.get('templates_id')

        if template_id:
            try:
                from apps.templates.models import Template
                template = Template.objects.get(id=template_id)
                data['subject'] = data.get('subject') or template.subject
                data['message'] = data.get('message') or template.content

            except Template.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Template with ID {template_id} not found.'
                }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        email_manager = serializer.instance

        send_now = request.data.get('send_now', True)
        if send_now and not email_manager.schedule_send:
            send_result = EmailManagerService.send_email(email_manager)
            if not send_result['success']:
                email_manager.refresh_from_db()
                serializer = self.get_serializer(email_manager)
                return Response({
                    'success': True,
                    'message': 'Email created but sending failed',
                    'data': serializer.data,
                    'send_error': send_result.get('error')
                }, status=status.HTTP_201_CREATED)
            email_manager.refresh_from_db()
            serializer = self.get_serializer(email_manager)

        headers = self.get_success_headers(serializer.data)
        return Response({
            'success': True,
            'message': 'Email manager entry created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'success': True,
            'message': 'Email manager entry updated successfully',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete(user=request.user)
        return Response({
            'success': True,
            'message': 'Email manager entry deleted successfully',
            'data': None
        }, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def get_all_emails(self, request):
        try:
            emails = self.get_queryset()
            serializer = self.get_serializer(emails, many=True)
            
            return Response({
                'success': True,
                'message': 'Email manager entries retrieved successfully',
                'data': serializer.data,
                'count': emails.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving email manager entries: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def scheduled_emails(self, request):
        try:
            scheduled_emails = EmailManager.objects.filter(
                schedule_send=True,
                is_deleted=False
            ).order_by('schedule_date_time')
            serializer = self.get_serializer(scheduled_emails, many=True)
            
            return Response({
                'success': True,
                'message': 'Scheduled emails retrieved successfully',
                'data': serializer.data,
                'count': scheduled_emails.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving scheduled emails: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def priorities(self, request):
        try:
            priorities = [
                {'value': choice[0], 'label': choice[1]} 
                for choice in EmailManager.PRIORITY_CHOICES
            ]
            return Response({
                'success': True,
                'message': 'Priority options retrieved successfully',
                'data': priorities
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving priority options: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        try:
            email_manager = self.get_object()
            
            if email_manager.email_status == 'sent':
                return Response({
                    'success': False,
                    'message': 'Email has already been sent',
                    'sent_at': email_manager.sent_at.isoformat() if email_manager.sent_at else None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = EmailManagerService.send_email(email_manager)
            
            if result['success']:
                email_manager.refresh_from_db()
                serializer = self.get_serializer(email_manager)
                return Response({
                    'success': True,
                    'message': result['message'],
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': result['message'],
                    'error': result.get('error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error sending email: {str(e)}',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def send_email(self, request):
        try:
            email_id = request.data.get('id') or request.query_params.get('id')
            
            if email_id:
                try:
                    email_manager = EmailManager.objects.get(id=email_id, is_deleted=False)
                except EmailManager.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': f'Email with ID {email_id} not found',
                        'error': 'Email does not exist'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if email_manager.email_status == 'sent':
                    return Response({
                        'success': False,
                        'message': 'Email has already been sent',
                        'sent_at': email_manager.sent_at.isoformat() if email_manager.sent_at else None
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                if not request.data.get('to'):
                    return Response({
                        'success': False,
                        'message': 'Required fields missing',
                        'error': 'Please provide "to" field to send a new email, or provide "id" to send an existing email'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                email_data = request.data.copy()
                if 'templates_id' in email_data:
                    email_data['template'] = email_data.pop('templates_id')

                policy_number = email_data.get('policy_number')
                context = {}

                if policy_number:
                    try:
                        policy = Policy.objects.get(policy_number=policy_number)
                        customer = policy.customer
                        context = {
                            'first_name': customer.first_name,
                            'last_name': customer.last_name,
                            'full_name': customer.full_name,
                            'policy_number': policy.policy_number,
                            'expiry_date': policy.end_date.strftime('%Y-%m-%d') if policy.end_date else '',
                            'premium_amount': policy.premium_amount,
                        }
                    except Policy.DoesNotExist:
                        pass

                template = None
                if email_data.get('template'):
                    try:
                        template = Template.objects.get(id=email_data['template'], is_active=True)
                    except (Template.DoesNotExist, ValueError, TypeError):
                        return Response({
                            'success': False,
                            'message': 'Template not found',
                            'error': f"Template with ID {email_data.get('template')} does not exist or is not active"
                        }, status=status.HTTP_404_NOT_FOUND)

                if template:
                    if not email_data.get('subject') and template.subject:
                        email_data['subject'] = template.subject
                    if not email_data.get('message') and template.content:
                        email_data['message'] = template.content
                    
                    if context:
                        subject_template = DjangoTemplate(email_data['subject'])
                        message_template = DjangoTemplate(email_data['message'])
                        
                        email_data['subject'] = subject_template.render(Context(context))
                        email_data['message'] = message_template.render(Context(context))

                if not email_data.get('subject'):
                    return Response({
                        'success': False,
                        'message': 'Required fields missing',
                        'error': 'Please provide "subject" field or a valid "template" with subject'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if not email_data.get('message'):
                    return Response({
                        'success': False,
                        'message': 'Required fields missing',
                        'error': 'Please provide "message" field or a valid "template" with content'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                create_serializer = EmailManagerCreateSerializer(data=email_data)
                if not create_serializer.is_valid():
                    return Response({
                        'success': False,
                        'message': 'Validation error',
                        'error': create_serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                email_manager = create_serializer.save(created_by=request.user)
                email_manager.from_email = "renewals@intelipro.in"
                email_manager.save(update_fields=['from_email'])

                if not email_manager.schedule_send:
                    email_manager.schedule_send = False
                    email_manager.save()
            
            email_manager.from_email = "renewals@intelipro.in"
            email_manager.save(update_fields=['from_email'])
            result = EmailManagerService.send_email(email_manager)
            
            if result['success']:
                email_manager.refresh_from_db()
                serializer = self.get_serializer(email_manager)
                return Response({
                    'success': True,
                    'message': result['message'],
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                email_manager.refresh_from_db()
                serializer = self.get_serializer(email_manager)
                return Response({
                    'success': False,
                    'message': result['message'],
                    'error': result.get('error'),
                    'data': serializer.data
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error sending email: {str(e)}',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def send_scheduled(self, request):
        try:
            result = EmailManagerService.send_scheduled_emails()
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': result['message'],
                    'sent_count': result.get('sent', 0),
                    'failed_count': result.get('failed', 0)
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': result['message'],
                    'error': result.get('error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error processing scheduled emails: {str(e)}',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def sent_emails(self, request):
        try:
            sent_emails = EmailManager.objects.filter(
                email_status='sent',
                is_deleted=False
            ).order_by('-sent_at')

            serializer = SentEmailListSerializer(sent_emails, many=True)

            return Response({
                'success': True,
                'message': 'Sent emails retrieved successfully',
                'count': sent_emails.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving sent emails: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=False, methods=['get'], url_path='email_details/(?P<pk>[^/.]+)')
    def email_details(self, request, pk=None):
        try:
            email = EmailManager.objects.get(id=pk, is_deleted=False)
            serializer = EmailManagerSerializer(email)

            renewal_info = {}
            if email.policy_number:
                try:
                    from apps.policies.models import Policy
                    policy = Policy.objects.get(policy_number=email.policy_number)
                    renewal_info = {
                        "policy_number": policy.policy_number,
                        "customer_name": policy.customer.full_name,
                        "renewal_date": policy.renewal_date.strftime("%Y-%m-%d") if policy.renewal_date else None,
                        "premium_amount": str(policy.premium_amount),
                    }
                except Policy.DoesNotExist:
                    renewal_info = {
                        "policy_number": email.policy_number,
                        "customer_name": email.customer_name,
                        "renewal_date": email.renewal_date,
                        "premium_amount": str(email.premium_amount) if email.premium_amount else None,
                    }

            tracking_info = {
                "opens": 0,
                "clicks": 0,
            }

            response_data = {
                "success": True,
                "message": "Email details retrieved successfully",
                "data": {
                    "email_info": {
                        **serializer.data,              
                        "from_email": email.from_email,   
                    },
                    "renewal_information": renewal_info,
                    "email_tracking": tracking_info,
                },
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except EmailManager.DoesNotExist:
            return Response({
                "success": False,
                "message": f"Email with ID {pk} not found"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error retrieving email details: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['get'])
    def started_emails(self, request):
        try:
            manager_emails = EmailManager.objects.filter(
                started=True,
                is_deleted=False
            ).order_by('-updated_at')

            manager_data = EmailManagerSerializer(manager_emails, many=True).data

            inbox_emails = EmailManagerInbox.objects.filter(
                started=True,
                is_deleted=False
            ).order_by('-updated_at')

            inbox_data = EmailManagerInboxSerializer(inbox_emails, many=True).data

            combined_data = {
                "email_manager": manager_data,
                "email_inbox": inbox_data
            }

            return Response({
                "success": True,
                "message": "Started emails fetched successfully",
                "count": {
                    "email_manager": len(manager_data),
                    "email_inbox": len(inbox_data),
                    "total": len(manager_data) + len(inbox_data)
                },
                "data": combined_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error retrieving started emails: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
    @action(detail=True, methods=['post'], url_path='update_started_status')
    def update_started_status(self, request, pk=None):
        try:
            email = self.get_object()
            started = request.data.get('started', False)
            email.started = started
            email.save()
            return Response({'success': True, 'message': 'Started status updated'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['get'], url_path='started_email_details')
    def started_email_details(self, request, pk=None):
        try:
            try:
                email = EmailManager.objects.get(id=pk, started=True, is_deleted=False)
                data = {
                    "type": "email_manager",
                    "details": EmailManagerSerializer(email).data
                }
                return Response({
                    "success": True,
                    "message": "Started email details fetched successfully",
                    "data": data
                }, status=status.HTTP_200_OK)
            except EmailManager.DoesNotExist:
                pass

            try:
                email_inbox = EmailManagerInbox.objects.get(id=pk, started=True, is_deleted=False)
                data = {
                    "type": "email_inbox",
                    "details": EmailManagerInboxSerializer(email_inbox).data
                }
                return Response({
                    "success": True,
                    "message": "Started inbox email details fetched successfully",
                    "data": data
                }, status=status.HTTP_200_OK)
            except EmailManagerInbox.DoesNotExist:
                pass

            return Response({
                "success": False,
                "message": f"No active started email found with ID {pk}"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error fetching details: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
    @action(detail=True, methods=['post'], url_path='reply')
    def reply_to_started_email(self, request, pk=None):
        try:
            message = request.data.get("message")
            html_message = request.data.get("html_message")

            if not message:
                return Response({
                    "success": False,
                    "message": "Message is required"
                }, status=400)

            original_email = None
            inbox_email = None
            try:
                original_email = EmailManager.objects.get(id=pk, started=True, is_deleted=False)
                to_email = original_email.to
                subject = f"Re: {original_email.subject}"
            except EmailManager.DoesNotExist:
                try:
                    inbox_email = EmailManagerInbox.objects.get(id=pk, started=True, is_deleted=False)
                    to_email = inbox_email.from_email
                    subject = f"Re: {inbox_email.subject}"
                except EmailManagerInbox.DoesNotExist:
                    return Response({
                        "success": False,
                        "message": f"No started email found with ID {pk}"
                    }, status=404)

            EmailManagerService.send_reply_smtp(
                to_email=to_email,
                subject=subject,
                message=message,
                html_message=html_message
            )

            reply_record = StartedReplyMail.objects.create(
                original_email_manager=original_email,
                original_inbox_email=inbox_email,
                to_email=to_email,
                subject=subject,
                message=message,
                html_message=html_message,
                created_by=request.user
            )

            return Response({
                "success": True,
                "message": "Reply sent successfully",
                "reply_id": reply_record.id
            }, status=200)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=500)    

class EmailManagerInboxViewSet(viewsets.ModelViewSet):
    queryset = EmailManagerInbox.objects.all()
    serializer_class = EmailManagerInboxSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = EmailManagerInbox.objects.filter(is_deleted=False)

        from_email = self.request.query_params.get('from_email')
        if from_email:
            queryset = queryset.filter(from_email__icontains=from_email)

        subject = self.request.query_params.get('subject')
        if subject:
            queryset = queryset.filter(subject__icontains=subject)

        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        return queryset

    @action(detail=False, methods=['get'], url_path='reply-emails')
    def reply_emails(self, request):
        try:
            reply_emails = self.get_queryset().exclude(in_reply_to__isnull=True).exclude(in_reply_to__exact='')

            serializer = self.get_serializer(reply_emails, many=True)

            return Response({
                'success': True,
                'message': 'Reply emails retrieved successfully',
                'count': reply_emails.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving reply emails: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=False, methods=['get'], url_path='fetch-replies')
    def fetch_replies(self, request):
        try:
            queryset = EmailManagerInbox.objects.filter(
                in_reply_to__isnull=False,
                is_deleted=False
            )

            # Optional filters
            related_email_id = request.query_params.get('related_email_id')
            if related_email_id:
                queryset = queryset.filter(related_email_id=related_email_id)

            policy_number = request.query_params.get('policy_number')
            if policy_number:
                queryset = queryset.filter(
                    related_email__policy_number__icontains=policy_number
                )

            from_email = request.query_params.get('from_email')
            if from_email:
                queryset = queryset.filter(from_email__icontains=from_email)

            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')

            if date_from:
                queryset = queryset.filter(received_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(received_at__lte=date_to)

            queryset = queryset.order_by('-received_at')

            serializer = self.get_serializer(queryset, many=True)

            return Response({
                'success': True,
                'message': 'Reply emails fetched successfully',
                'count': queryset.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error fetching reply emails: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   

    @action(detail=True, methods=['get'], url_path='email_details')
    def email_details(self, request, pk=None):
        try:
            email = self.get_object()
            serializer = self.get_serializer(email)

            ai_analysis = analyze_email_sentiment_and_intent(email.message or email.html_message or "")

            related_info = {}
            if email.related_email:
                related = email.related_email
                related_info = {
                    "policy_number": related.policy_number,
                    "customer_name": related.customer_name,
                    "renewal_date": related.renewal_date.strftime("%Y-%m-%d") if related.renewal_date else None,
                    "premium_amount": str(related.premium_amount) if related.premium_amount else None,
                    "priority": related.priority,  
                }

            response_data = {
                "id": email.id,
                "from_email": email.from_email,
                "to_email": email.to_email,
                "subject": email.subject,
                "message": serializer.data.get("message"),
                "html_message": serializer.data.get("html_message"),
                "clean_text": serializer.data.get("clean_text"),
                "received_at": email.received_at.isoformat() if email.received_at else None,  
                "policy_info": related_info,
                "priority": related_info.get("priority"),
                "sentiment": ai_analysis.get("sentiment", "neutral (50%)"),
                "intent": ai_analysis.get("intent", "unknown"),  
            }

            return Response({
                "success": True,
                "message": "Inbox email details retrieved successfully",
                "data": response_data
            }, status=status.HTTP_200_OK)

        except EmailManagerInbox.DoesNotExist:
            return Response({
                "success": False,
                "message": f"Inbox email with ID {pk} not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error retrieving inbox email: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics(self, request):
        try:
            total_emails = EmailManagerInbox.objects.filter(is_deleted=False).count()
            unread_emails = EmailManagerInbox.objects.filter(
                is_read=False, is_deleted=False
            ).count()

            sent_count = EmailManager.objects.filter(email_status="sent", is_deleted=False).count()
            replied_count = EmailManagerInbox.objects.filter(
                related_email__isnull=False, is_deleted=False
            ).count()

            response_rate = f"{round((replied_count / sent_count) * 100, 2)}%" if sent_count > 0 else "0%"

            replies = EmailManagerInbox.objects.filter(
                related_email__isnull=False,
                related_email__sent_at__isnull=False,
                is_deleted=False
            ).annotate(
                response_time=ExpressionWrapper(
                    F('received_at') - F('related_email__sent_at'),
                    output_field=DurationField()
                )
            )

            avg_response = replies.aggregate(Avg('response_time'))['response_time__avg']
            avg_response_str = f"{round(avg_response.total_seconds() / 3600, 2)}h" if avg_response else "0h"

            top_senders = list(
                EmailManagerInbox.objects.filter(is_deleted=False)
                .values("from_email")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            )

            positive = neutral = negative = 0

            inbox_emails = EmailManagerInbox.objects.filter(is_deleted=False)

            for email_obj in inbox_emails:

                raw_text = email_obj.html_message or email_obj.message or ""
                raw_text = raw_text.strip()

                if not raw_text or len(raw_text) < 5:
                    continue

                import re
                raw_text = re.sub(r"<(script|style).*?>.*?</\\1>", "", raw_text, flags=re.S)

                print("AI INPUT (FIRST 300 CHARS):", raw_text[:300])

                result = analyze_email_sentiment_and_intent(raw_text)
                sentiment_full = result.get("sentiment", "").lower()

                if "positive" in sentiment_full:
                    positive += 1
                elif "negative" in sentiment_full:
                    negative += 1
                else:
                    neutral += 1

            total_sentiment = positive + neutral + negative

            if total_sentiment == 0:
                sentiment_summary = {
                    "positive": "0%",
                    "neutral": "0%",
                    "negative": "0%"
                }
            else:
                sentiment_summary = {
                    "positive": f"{round((positive / total_sentiment) * 100, 2)}%",
                    "neutral": f"{round((neutral / total_sentiment) * 100, 2)}%",
                    "negative": f"{round((negative / total_sentiment) * 100, 2)}%",
                }

            return Response({
                "success": True,
                "message": "Analytics fetched successfully",
                "data": {
                    "total_emails": total_emails,
                    "unread_emails": unread_emails,
                    "response_rate": response_rate,
                    "avg_response_time_hours": avg_response_str,
                    "top_senders": top_senders,
                    "sentiment": sentiment_summary
                }
            })

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error generating analytics: {str(e)}"
            }, status=500)


        
    @action(detail=True, methods=['patch'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        try:
            email_obj = self.get_object()
            email_obj.is_read = True
            email_obj.save()

            return Response({
                "success": True,
                "message": "Email marked as read successfully"
            }, status=200)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error marking email as read: {str(e)}"
            }, status=500)


    @action(detail=True, methods=['post'], url_path='reply')
    def reply_email(self, request, pk=None):
        try:
            inbox = self.get_object()
            serializer = EmailReplySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            message = serializer.validated_data.get("message")
            html_message = serializer.validated_data.get("html_message")
            template_id = serializer.validated_data.get("template_id")

            if template_id:
                try:
                    template = Template.objects.get(id=template_id)

                    context_data = {
                        "first_name": inbox.related_email.customer_name if inbox.related_email else "",
                        "policy_number": inbox.related_email.policy_number if inbox.related_email else "",
                        "expiry_date": inbox.related_email.renewal_date if inbox.related_email else "",
                        "premium_amount": inbox.related_email.premium_amount if inbox.related_email else "",
                        "agent_name": "Agent"
                    }

                    message = DjangoTemplate(template.content).render(Context(context_data))
                    html_message = message  

                except Template.DoesNotExist:
                    return Response({"error": "Template not found"}, status=400)


            if not message:
                return Response({"error": "No message available to send"}, status=400)

            reply = EmailReply.objects.create(
                inbox=inbox,
                to_email=inbox.from_email,
                from_email="renewals@intelipro.in",
                subject=f"Re: {inbox.subject}",
                message=message,
                html_message=html_message,
                in_reply_to=inbox.message_id,
                created_by=request.user
            )

            EmailManagerService.send_reply_email(reply)

            EmailManager.objects.create(
                to=reply.to_email,
                from_email="renewals@intelipro.in",
                subject=reply.subject,
                message=reply.message,
                email_status="sent",
                message_id=reply.message_id,
                sent_at=reply.sent_at,
                policy_number=inbox.related_email.policy_number if inbox.related_email else None,
                customer_name=inbox.related_email.customer_name if inbox.related_email else None,
                renewal_date=inbox.related_email.renewal_date if inbox.related_email else None,
                premium_amount=inbox.related_email.premium_amount if inbox.related_email else None,
                template_id=template_id if template_id else None,
                created_by=request.user
            )


            return Response({
                "success": True,
                "message": "Reply sent successfully",
                "reply_id": reply.id
            })

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error sending reply: {str(e)}"
            }, status=500)
        
    @action(detail=True, methods=['patch'], url_path='update-started-status')
    def update_started_status(self, request, pk=None):
        try:
            inbox_email = self.get_object()
            started = request.data.get('started')

            if started is None:
                return Response({
                    "success": False,
                    "message": "'started' field is required (true/false)"
                }, status=status.HTTP_400_BAD_REQUEST)

            inbox_email.started = bool(started)
            inbox_email.save(update_fields=['started'])

            return Response({
                "success": True,
                "message": "Started status updated successfully",
                "email_id": inbox_email.id,
                "started": inbox_email.started
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error updating started status: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


class SyncEmailsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            result = EmailInboxService.fetch_incoming_emails()
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'Emails synced successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to sync emails'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
       