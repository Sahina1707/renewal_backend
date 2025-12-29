from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import EmailProviderConfig, EmailProviderHealthLog, EmailProviderUsageLog, EmailProviderTestResult
from .serializers import (
    EmailProviderConfigSerializer, EmailProviderConfigCreateSerializer,
    EmailProviderConfigUpdateSerializer, EmailProviderCredentialsSerializer,
    EmailProviderHealthLogSerializer, EmailProviderUsageLogSerializer,
    EmailProviderTestResultSerializer, EmailProviderTestSerializer,
    EmailProviderStatsSerializer
)
from .services import EmailProviderService
from apps.billing.models import CommunicationLog


class EmailProviderConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email provider configurations"""
    
    queryset = EmailProviderConfig.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EmailProviderConfigCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EmailProviderConfigUpdateSerializer
        elif self.action == 'update_credentials':
            return EmailProviderCredentialsSerializer
        return EmailProviderConfigSerializer
    
    def get_queryset(self):
        """Filter providers based on query parameters"""
        queryset = super().get_queryset()
        
        # Ensure soft-deleted providers are excluded
        queryset = queryset.filter(is_deleted=False)
        
        # Filter by provider type
        provider_type = self.request.query_params.get('provider_type')
        if provider_type:
            queryset = queryset.filter(provider_type=provider_type)
        
        # Filter by health status
        health_status = self.request.query_params.get('health_status')
        if health_status:
            queryset = queryset.filter(health_status=health_status)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        return queryset.order_by('priority', 'name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new provider"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating a provider"""
        serializer.save(updated_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete the provider and return success message"""
        instance = self.get_object()
        provider_name = instance.name
        
        # Perform soft delete
        instance.soft_delete()
        instance.deleted_by = request.user
        instance.save(update_fields=['deleted_by'])
        
        return Response({
            'success': True,
            'message': f'Provider "{provider_name}" deleted successfully'
        }, status=status.HTTP_200_OK)
    
    def perform_destroy(self, instance):
        """Soft delete the provider"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def update_credentials(self, request, pk=None):
        """Update provider credentials"""
        provider = self.get_object()
        serializer = self.get_serializer(provider, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test email provider configuration"""
        provider = self.get_object()
        serializer = EmailProviderTestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        test_email = serializer.validated_data['test_email']
        service = EmailProviderService()
        
        # Test the provider
        result = service.test_provider(provider, test_email)
        
        # Create test result record
        EmailProviderTestResult.objects.create(
            provider=provider,
            test_email=test_email,
            status='success' if result['success'] else 'failed',
            error_message=result.get('error'),
            response_time=result.get('response_time'),
            tested_by=request.user
        )
        
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def health_check(self, request, pk=None):
        """Perform health check on provider"""
        provider = self.get_object()
        service = EmailProviderService()
        
        is_healthy = service.check_provider_health(provider)
        
        return Response({
            'provider_id': provider.id,
            'provider_name': provider.name,
            'is_healthy': is_healthy,
            'health_status': provider.health_status,
            'last_health_check': provider.last_health_check
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a provider"""
        provider = self.get_object()
        provider.is_active = True
        provider.updated_by = request.user
        provider.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Provider activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a provider"""
        provider = self.get_object()
        provider.is_active = False
        provider.updated_by = request.user
        provider.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Provider deactivated successfully'})
    
    @action(detail=True, methods=['post'])
    def reset_usage(self, request, pk=None):
        """Reset usage counters for a provider"""
        provider = self.get_object()
        reset_type = request.data.get('type', 'daily')  # daily or monthly
        
        if reset_type == 'daily':
            provider.reset_daily_usage()
        elif reset_type == 'monthly':
            provider.reset_monthly_usage()
        else:
            return Response(
                {'error': 'Invalid reset type. Use "daily" or "monthly"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({'message': f'{reset_type.title()} usage reset successfully'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics for all providers"""
        providers = self.get_queryset()
        service = EmailProviderService()
        
        stats = []
        for provider in providers:
            # Calculate usage percentages
            daily_usage_pct = (provider.emails_sent_today / provider.daily_limit * 100) if provider.daily_limit > 0 else 0
            monthly_usage_pct = (provider.emails_sent_this_month / provider.monthly_limit * 100) if provider.monthly_limit > 0 else 0
            
            # Get recent usage logs for success rate and response time
            recent_logs = EmailProviderUsageLog.objects.filter(
                provider=provider,
                logged_at__gte=timezone.now() - timedelta(days=7)
            )
            
            total_emails = sum(log.emails_sent for log in recent_logs)
            total_success = sum(log.success_count for log in recent_logs)
            total_response_time = sum(log.total_response_time for log in recent_logs)
            
            success_rate = (total_success / total_emails * 100) if total_emails > 0 else 0
            avg_response_time = (total_response_time / total_success) if total_success > 0 else 0
            
            stats.append({
                'provider_id': provider.id,
                'provider_name': provider.name,
                'provider_type': provider.provider_type,
                'is_active': provider.is_active,
                'health_status': provider.health_status,
                'emails_sent_today': provider.emails_sent_today,
                'emails_sent_this_month': provider.emails_sent_this_month,
                'daily_limit': provider.daily_limit,
                'monthly_limit': provider.monthly_limit,
                'daily_usage_percentage': round(daily_usage_pct, 2),
                'monthly_usage_percentage': round(monthly_usage_pct, 2),
                'last_health_check': provider.last_health_check,
                'success_rate': round(success_rate, 2),
                'average_response_time': round(avg_response_time, 3)
            })
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def health_status(self, request):
        """Get health status of all providers"""
        providers = self.get_queryset()
        service = EmailProviderService()
        
        health_data = []
        for provider in providers:
            is_healthy = service.check_provider_health(provider)
            health_data.append({
                'provider_id': provider.id,
                'provider_name': provider.name,
                'provider_type': provider.provider_type,
                'is_healthy': is_healthy,
                'health_status': provider.health_status,
                'last_health_check': provider.last_health_check,
                'can_send_email': provider.can_send_email()
            })
        
        return Response(health_data)


class EmailProviderHealthLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email provider health logs"""
    
    queryset = EmailProviderHealthLog.objects.all()
    serializer_class = EmailProviderHealthLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter health logs based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by provider
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        # Filter by health status
        is_healthy = self.request.query_params.get('is_healthy')
        if is_healthy is not None:
            queryset = queryset.filter(is_healthy=is_healthy.lower() == 'true')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(checked_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(checked_at__lte=end_date)
        
        return queryset.order_by('-checked_at')


class EmailProviderUsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email provider usage logs"""
    
    queryset = EmailProviderUsageLog.objects.all()
    serializer_class = EmailProviderUsageLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter usage logs based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by provider
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(logged_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(logged_at__lte=end_date)
        
        return queryset.order_by('-logged_at')


class EmailProviderTestResultViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email provider test results"""
    
    queryset = EmailProviderTestResult.objects.all()
    serializer_class = EmailProviderTestResultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter test results based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by provider
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by test email
        test_email = self.request.query_params.get('test_email')
        if test_email:
            queryset = queryset.filter(test_email__icontains=test_email)
        
        return queryset.order_by('-tested_at')


class EmailWebhookView(APIView):
    """
    Handle incoming webhooks from Email Providers (SendGrid, etc.) to update Billing Status.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider_type=None):
        if provider_type == 'sendgrid':
            events = request.data
            # SendGrid sends an array of events
            if isinstance(events, list):
                for event in events:
                    # SendGrid Message ID often has extra data appended, split by '.'
                    sg_message_id = event.get('sg_message_id', '').split('.')[0]
                    event_type = event.get('event')
                    
                    if sg_message_id and event_type:
                        # Map SendGrid events to Billing Status
                        new_status = None
                        if event_type in ['delivered', 'open', 'click']:
                            new_status = 'delivered'
                        elif event_type in ['bounce', 'dropped', 'spamreport']:
                            new_status = 'failed'
                        
                        if new_status:
                            # Update the log in Billing
                            CommunicationLog.objects.filter(
                                provider_message_id__startswith=sg_message_id
                            ).update(status=new_status)
                        
        return Response(status=status.HTTP_200_OK)
