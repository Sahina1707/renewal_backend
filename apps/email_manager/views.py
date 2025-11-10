from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import EmailManager
from .serializers import (
    EmailManagerSerializer,
    EmailManagerCreateSerializer,
    EmailManagerUpdateSerializer,
    SentEmailListSerializer
)
from .services import EmailManagerService
from apps.templates.models import Template
from apps.customer_payment_schedule.models import PaymentSchedule

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

                from apps.policies.models import Policy
                from django.template import Template as DjangoTemplate, Context

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
                if not email_manager.schedule_send:
                    email_manager.schedule_send = False
                    email_manager.save()
            
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
        """
        List all sent emails with policy number, priority, sent date, and due date.
        """
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
                    "email_info": serializer.data,
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