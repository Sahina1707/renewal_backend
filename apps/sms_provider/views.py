from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.http import HttpResponse
from django.utils import timezone
from .models import SmsProvider, SmsMessage
from .serializers import (
    SmsProviderSerializer,
    SmsProviderCreateUpdateSerializer,
    SmsMessageSerializer
)
from .services import SmsService


class SmsProviderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing SMS Providers.
    """
    queryset = SmsProvider.objects.filter(is_deleted=False)
    permission_classes = [permissions.IsAuthenticated] # type: ignore

    def get_serializer_class(self):
        """Return different serializers for read vs. write actions."""
        if self.action in ['create', 'update', 'partial_update']:
            return SmsProviderCreateUpdateSerializer
        return SmsProviderSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        # Soft delete
        instance.is_deleted = True
        instance.is_active = False
        instance.save()

    # --- 1. Health Check Action ---
    @action(detail=True, methods=['post'], url_path='health-check')
    def health_check(self, request, pk=None):
        """
        Endpoint: POST /api/sms_provider/providers/{id}/health-check/
        """
        provider = self.get_object()
        try:
            service = SmsService().get_service_instance(provider.id)
            # We need to call the health_check method we just added to services.py
            # Since the factory returns the specific class, we can call it directly.
            if hasattr(service, 'health_check'):
                result = service.health_check()
            else:
                result = {'status': 'unknown', 'error': 'Health check not implemented for this provider'}

            # Update DB status
            provider.status = result.get('status', 'disconnected')
            provider.last_sent_at = timezone.now() # Using this to track check time for now
            provider.save(update_fields=['status', 'last_sent_at'])
            
            return Response(result)
        except Exception as e:
            return Response({'status': 'disconnected', 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # --- 2. Set Default Action (Now using PATCH) ---
    # We change methods=['post'] to methods=['patch']
    @action(detail=True, methods=['patch'], url_path='set-default')
    def set_default(self, request, pk=None):
        """
        Endpoint: PATCH /api/sms_provider/providers/{id}/set-default/
        Body: {"is_default": true} or {"is_default": false}
        """
        provider = self.get_object()
        
        # Get the value from the request. If missing, assume True (Action style) or error.
        # Since it's PATCH, we should check if the field is actually present.
        desired_state = request.data.get('is_default')

        if desired_state is None:
             # If they didn't send data, default to True (Classic "Star button" behavior)
             desired_state = True

        # Validation: Cannot set inactive provider as default
        if desired_state and not provider.is_active:
            return Response(
                {"error": "Cannot set an inactive provider as default."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Apply the change
        provider.is_default = desired_state
        provider.save()
        return Response(SmsProviderSerializer(provider).data)

    # --- 3. Toggle Active Action (The Switch) ---
    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """
        Endpoint: POST /api/sms_provider/providers/{id}/toggle-active/
        """
        provider = self.get_object()
        provider.is_active = not provider.is_active
        
        # If we are deactivating the default provider, warn or handle it?
        # For now, just save.
        provider.save()
        return Response(SmsProviderSerializer(provider).data)


class SmsMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing SMS message logs.
    """
    queryset = SmsMessage.objects.all()
    serializer_class = SmsMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['provider', 'status', 'to_phone_number']
    search_fields = ['content', 'to_phone_number', 'message_sid']


class TwilioWebhookView(APIView):
    """
    Handle incoming status updates from Twilio.
    Twilio sends data as FORM-URLENCODED, not JSON.
    """
    permission_classes = [AllowAny] # Twilio doesn't use your JWT token
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        # Twilio sends data in request.POST
        message_sid = request.POST.get('MessageSid')
        message_status = request.POST.get('MessageStatus') # queued, sent, delivered, undelivered, failed
        error_code = request.POST.get('ErrorCode')
        
        print(f"📩 TWILIO WEBHOOK: {message_sid} -> {message_status}")

        if message_sid and message_status:
            try:
                # Find the message by the SID we saved earlier
                sms_obj = SmsMessage.objects.get(message_sid=message_sid)
                
                # Update status
                sms_obj.status = message_status
                
                if error_code:
                    sms_obj.error_code = error_code
                    sms_obj.error_message = "Twilio Error Code: " + str(error_code)
                
                # Set timestamps
                if message_status == 'sent':
                    sms_obj.sent_at = timezone.now()
                elif message_status == 'delivered':
                    sms_obj.delivered_at = timezone.now()
                
                sms_obj.save()
                
            except SmsMessage.DoesNotExist:
                print(f"⚠️ Message SID {message_sid} not found in local DB.")
        
        # Twilio expects an XML response or just 200 OK
        return HttpResponse("<Response></Response>", content_type="text/xml")
