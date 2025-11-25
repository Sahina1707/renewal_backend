#
# apps/whatsapp_provider/views.py
#
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model
import logging
import uuid

from .models import (
    WhatsAppProvider,
    WhatsAppPhoneNumber,
    WhatsAppMessageTemplate,
    WhatsAppMessage,
    WhatsAppWebhookEvent,
    WhatsAppFlow,
    WhatsAppAccountHealthLog,
    WhatsAppAccountUsageLog,
)
from .serializers import (
    WhatsAppProviderSerializer,
    WhatsAppProviderCreateUpdateSerializer,
    WhatsAppPhoneNumberSerializer,
    WhatsAppMessageTemplateSerializer,
    WhatsAppMessageSerializer,
    MessageSendSerializer,
    WhatsAppWebhookEventSerializer,
    WhatsAppFlowSerializer,
    WhatsAppAccountHealthLogSerializer,
    WhatsAppAccountUsageLogSerializer,
    TemplateProviderLinkSerializer
)
from .services import WhatsAppService, WhatsAppAPIError

User = get_user_model()
logger = logging.getLogger(__name__)


class WhatsAppProviderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing WhatsApp Providers (Meta, Twilio, etc.)
    """
    queryset = WhatsAppProvider.objects.filter(is_deleted=False)
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WhatsAppProviderCreateUpdateSerializer
        return WhatsAppProviderSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)
        return queryset.select_related('created_by', 'updated_by').prefetch_related(
            'phone_numbers', 'message_templates'
        )
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    
    @action(detail=True, methods=['post'], url_path='health-check')
    def health_check(self, request, pk=None):
        provider_model = self.get_object()
        
        try:
            service_factory = WhatsAppService()
            provider_service = service_factory.get_service_instance(provider_id=provider_model.id)
            
            result = provider_service.health_check()
            
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Health check failed for provider {pk}: {e}")
            return Response(
                {'status': 'unhealthy', 'error': f'Health check failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='analytics')
    def analytics(self, request, pk=None):
        provider = self.get_object()
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        try:
            service = WhatsAppService()
            analytics_data = service.get_analytics(provider, start_date, end_date)
            return Response(analytics_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Analytics failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='send-message')
    def send_message(self, request, pk=None):
        provider_model = self.get_object()
        
        serializer = MessageSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        validated_data = serializer.validated_data
        
        try:
            service_factory = WhatsAppService()
            
            provider_service = service_factory.get_service_instance(provider_id=provider_model.id)
            
            message_type = validated_data['message_type']
            to_phone = validated_data['to_phone_number']
            
            kwargs = {
                'customer_id': validated_data.get('customer_id'),
                'campaign_id': validated_data.get('campaign_id'),
            }

            response = {}
            if message_type == 'text':
                response = provider_service.send_text_message(
                    to_phone=to_phone,
                    text_content=validated_data['text_content'],
                    **kwargs
                )
            
            elif message_type == 'template':
                try:
                    template = WhatsAppMessageTemplate.objects.get(
                        id=validated_data['template_id'],
                        provider=provider_model,
                        status='approved'
                    )
                except WhatsAppMessageTemplate.DoesNotExist:
                    raise WhatsAppAPIError("Template not found, not approved, or does not belong to this provider.")
                
                response = provider_service.send_template_message(
                    to_phone=to_phone,
                    template=template,
                    template_params=validated_data['template_params'],
                    **kwargs
                )
            
            elif message_type == 'interactive':
                try:
                    flow = WhatsAppFlow.objects.get(
                        id=validated_data['flow_id'],
                        provider=provider_model,
                        status='published'
                    )
                except WhatsAppFlow.DoesNotExist:
                    raise WhatsAppAPIError("Flow not found, not published, or does not belong to this provider.")

                response = provider_service.send_interactive_message(
                    to_phone=to_phone,
                    flow=flow,
                    flow_token=validated_data.get('flow_token'),
                    **kwargs
                )
                
            return Response(response, status=status.HTTP_200_OK)
            
        except WhatsAppAPIError as e:
            return Response({'error': f'Failed to send message: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error sending message via provider {pk}: {e}", exc_info=True)
            return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhatsAppPhoneNumberViewSet(viewsets.ModelViewSet):
    queryset = WhatsAppPhoneNumber.objects.all()
    serializer_class = WhatsAppPhoneNumberSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by provider
        provider_id = self.request.query_params.get('provider')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(provider__created_by=self.request.user)
        
        return queryset.select_related('provider')


class WhatsAppMessageTemplateViewSet(viewsets.ModelViewSet):
    queryset = WhatsAppMessageTemplate.objects.all()
    serializer_class = WhatsAppMessageTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        provider_id = self.request.query_params.get('provider')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(provider__created_by=self.request.user)
        
        return queryset.select_related('provider', 'created_by')
    
    
    @action(detail=True, methods=['post'], url_path='submit-for-approval')
    def submit_for_approval(self, request, pk=None):
        template = self.get_object()
        if template.provider.provider_type != 'meta':
            return Response(
                {'error': 'This action is only available for Meta providers.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {'message': 'Template submission logic needs to be implemented in MetaProviderService.'}, 
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class WhatsAppMessageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WhatsAppMessage.objects.all()
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['direction', 'message_type', 'status', 'provider', 'phone_number']
    search_fields = ['message_id', 'to_phone_number', 'from_phone_number']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(provider__created_by=self.request.user)
        
        return queryset.select_related(
            'provider', 'phone_number', 'template', 'campaign', 'customer'
        )


class WhatsAppWebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WhatsAppWebhookEvent.objects.all()
    serializer_class = WhatsAppWebhookEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['event_type', 'processed', 'provider']
    ordering = ['-received_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(provider__created_by=self.request.user)
        return queryset.select_related('provider', 'message')


class WhatsAppFlowViewSet(viewsets.ModelViewSet):
    queryset = WhatsAppFlow.objects.all()
    serializer_class = WhatsAppFlowSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        provider_id = self.request.query_params.get('provider')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(provider__created_by=self.request.user)
        
        return queryset.select_related('provider', 'created_by')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WhatsAppWebhookView(viewsets.ViewSet):
    permission_classes = []  
    parser_classes = [JSONParser]
    
    @action(detail=False, methods=['get'], url_path='(?P<provider_id>[0-9]+)')
    def verify_webhook(self, request, provider_id=None):
        logger.info(f"Webhook verification attempt for provider ID: {provider_id}")
        
        try:
            service_factory = WhatsAppService()
            provider_service = service_factory.get_service_instance_for_webhook(provider_id=provider_id)
            provider = provider_service.provider

            if provider.provider_type == 'meta':
                hub_mode = request.GET.get('hub.mode')
                hub_challenge = request.GET.get('hub.challenge')
                hub_verify_token = request.GET.get('hub.verify_token')
                
                expected_token = provider.webhook_verify_token
                
                if hub_mode == 'subscribe' and hub_verify_token == expected_token:
                    logger.info(f"Webhook verified for Meta provider: {provider.name}")
                    return Response(int(hub_challenge), status=status.HTTP_200_OK)
                else:
                    logger.warning(f"Webhook verification FAILED for Meta provider: {provider.name}. Token mismatch.")
                    return Response('Invalid token', status=status.HTTP_403_FORBIDDEN)
            
            
            logger.warning(f"GET request received for non-Meta provider {provider.name}, not supported.")
            return Response('Provider not configured for GET webhook', status=status.HTTP_400_BAD_REQUEST)

        except WhatsAppAPIError as e:
            return Response(str(e), status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Webhook verification error: {e}", exc_info=True)
            return Response('Internal error', status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='(?P<provider_id>[0-9]+)')
    def handle_webhook(self, request, provider_id=None):
        logger.info(f"Received webhook POST for provider ID: {provider_id}")
        try:
            service_factory = WhatsAppService()
            provider_service = service_factory.get_service_instance_for_webhook(provider_id=provider_id)
            
            provider_service.handle_webhook(request.data)
            
            return Response({'status': 'success'}, status=status.HTTP_200_OK)
            
        except WhatsAppAPIError as e:
            return Response(str(e), status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}", exc_info=True)
            return Response({'error': 'Webhook processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhatsAppAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """Get dashboard analytics."""
        user = request.user
        
        if user.is_staff:
            provider_qs = WhatsAppProvider.objects.filter(is_deleted=False)
        else:
            provider_qs = WhatsAppProvider.objects.filter(
                created_by=user, is_deleted=False
            )
        
        total_accounts = provider_qs.count()
        active_accounts = provider_qs.filter(is_active=True, status__in=['connected', 'verified']).count()
        
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_messages = WhatsAppMessage.objects.filter(
            provider__in=provider_qs,
            created_at__gte=thirty_days_ago
        )
        
        total_messages = recent_messages.count()
        sent_messages = recent_messages.filter(direction='outbound').count()
        received_messages = recent_messages.filter(direction='inbound').count()
        
        delivered_messages = recent_messages.filter(status='delivered').count()
        read_messages = recent_messages.filter(status='read').count()
        failed_messages = recent_messages.filter(status='failed').count()
        
        total_templates = WhatsAppMessageTemplate.objects.filter(provider__in=provider_qs).count()
        approved_templates = WhatsAppMessageTemplate.objects.filter(
            provider__in=provider_qs, status='approved'
        ).count()
        
        return Response({
            'accounts': {'total': total_accounts, 'active': active_accounts},
            'messages_30_days': {
                'total': total_messages, 'sent': sent_messages, 'received': received_messages,
                'delivered': delivered_messages, 'read': read_messages, 'failed': failed_messages,
                'delivery_rate': (delivered_messages / sent_messages * 100) if sent_messages > 0 else 0,
                'read_rate': (read_messages / delivered_messages * 100) if delivered_messages > 0 else 0
            },
            'templates': {'total': total_templates, 'approved': approved_templates}
        }, status=status.HTTP_200_OK)