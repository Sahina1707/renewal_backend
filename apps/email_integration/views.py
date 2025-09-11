from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta

from .models import (
    EmailWebhook, EmailAutomation, EmailAutomationLog, EmailIntegration,
    EmailSLA, EmailTemplateVariable, EmailIntegrationAnalytics
)
from .serializers import (
    EmailWebhookSerializer, EmailAutomationSerializer, EmailAutomationLogSerializer,
    EmailIntegrationSerializer, EmailSLASerializer, EmailTemplateVariableSerializer,
    EmailIntegrationAnalyticsSerializer, WebhookProcessSerializer, AutomationExecuteSerializer,
    IntegrationSyncSerializer, DynamicTemplateCreateSerializer, EmailScheduleSerializer,
    EmailReminderSerializer, EmailSignatureSerializer, SLAStatisticsSerializer,
    IntegrationStatisticsSerializer
)
from .services import EmailIntegrationService


class EmailWebhookViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing email webhooks"""
    
    queryset = EmailWebhook.objects.all()
    serializer_class = EmailWebhookSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter webhooks based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by provider
        provider = self.request.query_params.get('provider')
        if provider:
            queryset = queryset.filter(provider=provider)
        
        # Filter by event type
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def process(self, request):
        """Process pending webhooks"""
        serializer = WebhookProcessSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        webhook_id = serializer.validated_data['webhook_id']
        force_process = serializer.validated_data['force_process']
        
        try:
            webhook = EmailWebhook.objects.get(id=webhook_id)
            
            if webhook.status != 'pending' and not force_process:
                return Response(
                    {'error': 'Webhook is not pending'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = EmailIntegrationService()
            result = service.process_webhook(
                webhook.provider,
                webhook.event_type,
                webhook.raw_data
            )
            
            if result['success']:
                return Response(result)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except EmailWebhook.DoesNotExist:
            return Response(
                {'error': 'Webhook not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """Reprocess a webhook"""
        webhook = self.get_object()
        
        service = EmailIntegrationService()
        result = service.process_webhook(
            webhook.provider,
            webhook.event_type,
            webhook.raw_data
        )
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class EmailAutomationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email automations"""
    
    queryset = EmailAutomation.objects.filter(is_deleted=False)
    serializer_class = EmailAutomationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter automations based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by trigger type
        trigger_type = self.request.query_params.get('trigger_type')
        if trigger_type:
            queryset = queryset.filter(trigger_type=trigger_type)
        
        # Filter by action type
        action_type = self.request.query_params.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        return queryset.order_by('-priority', 'name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new automation"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating an automation"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the automation"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute an automation"""
        automation = self.get_object()
        serializer = AutomationExecuteSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        trigger_data = serializer.validated_data.get('trigger_data', {})
        force_execute = serializer.validated_data.get('force_execute', False)
        
        service = EmailIntegrationService()
        result = service.execute_automation(
            str(automation.id),
            trigger_data
        )
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an automation"""
        automation = self.get_object()
        automation.status = 'active'
        automation.is_active = True
        automation.updated_by = request.user
        automation.save(update_fields=['status', 'is_active', 'updated_by'])
        
        return Response({'message': 'Automation activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an automation"""
        automation = self.get_object()
        automation.status = 'inactive'
        automation.is_active = False
        automation.updated_by = request.user
        automation.save(update_fields=['status', 'is_active', 'updated_by'])
        
        return Response({'message': 'Automation deactivated successfully'})
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get automation execution logs"""
        automation = self.get_object()
        logs = EmailAutomationLog.objects.filter(automation=automation).order_by('-created_at')
        
        # Apply pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        logs_page = logs[start:end]
        total_count = logs.count()
        
        serializer = EmailAutomationLogSerializer(logs_page, many=True)
        
        return Response({
            'results': serializer.data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get automation statistics"""
        queryset = self.get_queryset()
        
        # Basic statistics
        total_automations = queryset.count()
        active_automations = queryset.filter(is_active=True).count()
        inactive_automations = queryset.filter(is_active=False).count()
        
        # Execution statistics
        total_executions = queryset.aggregate(
            total=models.Sum('execution_count')
        )['total'] or 0
        
        # Recent executions
        recent_executions = EmailAutomationLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Success rate
        successful_executions = EmailAutomationLog.objects.filter(
            status='completed',
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        total_recent_executions = EmailAutomationLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        success_rate = (successful_executions / total_recent_executions * 100) if total_recent_executions > 0 else 0
        
        return Response({
            'total_automations': total_automations,
            'active_automations': active_automations,
            'inactive_automations': inactive_automations,
            'total_executions': total_executions,
            'recent_executions': recent_executions,
            'success_rate': round(success_rate, 2)
        })


class EmailAutomationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing automation logs"""
    
    queryset = EmailAutomationLog.objects.all()
    serializer_class = EmailAutomationLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter logs based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by automation
        automation_id = self.request.query_params.get('automation_id')
        if automation_id:
            queryset = queryset.filter(automation_id=automation_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')


class EmailIntegrationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email integrations"""
    
    queryset = EmailIntegration.objects.filter(is_deleted=False)
    serializer_class = EmailIntegrationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter integrations based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by integration type
        integration_type = self.request.query_params.get('integration_type')
        if integration_type:
            queryset = queryset.filter(integration_type=integration_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by sync enabled
        sync_enabled = self.request.query_params.get('sync_enabled')
        if sync_enabled is not None:
            queryset = queryset.filter(sync_enabled=sync_enabled.lower() == 'true')
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new integration"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating an integration"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the integration"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Sync integration data"""
        integration = self.get_object()
        serializer = IntegrationSyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        sync_type = serializer.validated_data.get('sync_type', 'incremental')
        force_sync = serializer.validated_data.get('force_sync', False)
        
        service = EmailIntegrationService()
        result = service.sync_integration(
            str(integration.id),
            sync_type
        )
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get integration status"""
        integration = self.get_object()
        
        return Response({
            'integration_id': str(integration.id),
            'name': integration.name,
            'status': integration.status,
            'last_sync': integration.last_sync,
            'last_error': integration.last_error,
            'error_count': integration.error_count,
            'sync_enabled': integration.sync_enabled,
            'auto_sync': integration.auto_sync
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get integration statistics"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        service = EmailIntegrationService()
        stats = service.get_integration_statistics(start_date, end_date)
        
        if 'error' in stats:
            return Response(stats, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(stats)


class EmailSLAViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email SLAs"""
    
    queryset = EmailSLA.objects.filter(is_deleted=False)
    serializer_class = EmailSLASerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter SLAs based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by SLA type
        sla_type = self.request.query_params.get('sla_type')
        if sla_type:
            queryset = queryset.filter(sla_type=sla_type)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('priority', 'name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new SLA"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating an SLA"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the SLA"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an SLA"""
        sla = self.get_object()
        sla.is_active = True
        sla.updated_by = request.user
        sla.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'SLA activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an SLA"""
        sla = self.get_object()
        sla.is_active = False
        sla.updated_by = request.user
        sla.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'SLA deactivated successfully'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get SLA statistics"""
        queryset = self.get_queryset()
        
        # Basic statistics
        total_slas = queryset.count()
        active_slas = queryset.filter(is_active=True).count()
        
        # SLA performance
        total_incidents = queryset.aggregate(
            total=models.Sum('total_incidents')
        )['total'] or 0
        
        met_sla_count = queryset.aggregate(
            total=models.Sum('met_sla_count')
        )['total'] or 0
        
        breached_sla_count = queryset.aggregate(
            total=models.Sum('breached_sla_count')
        )['total'] or 0
        
        # Calculate overall SLA performance
        if total_incidents > 0:
            sla_performance = (met_sla_count / total_incidents) * 100
        else:
            sla_performance = 100
        
        return Response({
            'total_slas': total_slas,
            'active_slas': active_slas,
            'total_incidents': total_incidents,
            'met_sla_count': met_sla_count,
            'breached_sla_count': breached_sla_count,
            'sla_performance': round(sla_performance, 2)
        })


class EmailTemplateVariableViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email template variables"""
    
    queryset = EmailTemplateVariable.objects.filter(is_deleted=False)
    serializer_class = EmailTemplateVariableSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter template variables based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by variable type
        variable_type = self.request.query_params.get('variable_type')
        if variable_type:
            queryset = queryset.filter(variable_type=variable_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by system variables
        is_system = self.request.query_params.get('is_system')
        if is_system is not None:
            queryset = queryset.filter(is_system=is_system.lower() == 'true')
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        """Set created_by when creating a new template variable"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating a template variable"""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the template variable"""
        instance.soft_delete()
        instance.deleted_by = self.request.user
        instance.save(update_fields=['deleted_by'])
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a template variable"""
        variable = self.get_object()
        variable.is_active = True
        variable.updated_by = request.user
        variable.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Template variable activated successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a template variable"""
        variable = self.get_object()
        variable.is_active = False
        variable.updated_by = request.user
        variable.save(update_fields=['is_active', 'updated_by'])
        
        return Response({'message': 'Template variable deactivated successfully'})
    
    @action(detail=True, methods=['post'])
    def increment_usage(self, request, pk=None):
        """Increment usage count for a template variable"""
        variable = self.get_object()
        variable.usage_count += 1
        variable.last_used = timezone.now()
        variable.save(update_fields=['usage_count', 'last_used'])
        
        return Response({
            'message': 'Usage count incremented',
            'usage_count': variable.usage_count,
            'last_used': variable.last_used
        })


class EmailIntegrationAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing integration analytics"""
    
    queryset = EmailIntegrationAnalytics.objects.all()
    serializer_class = EmailIntegrationAnalyticsSerializer
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
        
        return queryset.order_by('-date')
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Get analytics trends"""
        queryset = self.get_queryset()
        
        # Get trends for the last 30 days
        trends = queryset.filter(
            date__gte=timezone.now().date() - timedelta(days=30)
        ).order_by('date')
        
        # Group by period type
        daily_trends = trends.filter(period_type='daily')
        weekly_trends = trends.filter(period_type='weekly')
        monthly_trends = trends.filter(period_type='monthly')
        
        return Response({
            'daily_trends': EmailIntegrationAnalyticsSerializer(daily_trends, many=True).data,
            'weekly_trends': EmailIntegrationAnalyticsSerializer(weekly_trends, many=True).data,
            'monthly_trends': EmailIntegrationAnalyticsSerializer(monthly_trends, many=True).data
        })
