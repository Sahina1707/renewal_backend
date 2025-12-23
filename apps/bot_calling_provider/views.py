from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    BotCallingProviderConfig,
    BotCallingProviderHealthLog,
    BotCallingProviderUsageLog,
    BotCallingProviderTestResult,
)

from .serializers import (
    BotCallingProviderConfigSerializer,
    BotCallingProviderConfigCreateSerializer,
    BotCallingProviderConfigUpdateSerializer,
    BotCallingProviderHealthLogSerializer,
    BotCallingProviderUsageLogSerializer,
    BotCallingProviderTestResultSerializer,
    BotCallingProviderTestSerializer,
    BotCallingProviderStatsSerializer,
)

from .services import BotCallingProviderService


# ============================================================
#  BOT CALLING PROVIDER CONFIG
# ============================================================

class BotCallingProviderConfigViewSet(viewsets.ModelViewSet):
    """
    Manage bot calling provider configurations.
    PATCH behavior matches call_provider exactly.
    """

    queryset = BotCallingProviderConfig.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]

    # --------------------------------------------------
    # Serializer selection
    # --------------------------------------------------
    def get_serializer_class(self):
        if self.action == 'create':
            return BotCallingProviderConfigCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return BotCallingProviderConfigUpdateSerializer
        return BotCallingProviderConfigSerializer

    # --------------------------------------------------
    # Queryset filters
    # --------------------------------------------------
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False)

        provider_type = self.request.query_params.get('provider_type')
        if provider_type:
            queryset = queryset.filter(provider_type=provider_type)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset.order_by('priority', 'name')

    # --------------------------------------------------
    # CREATE
    # --------------------------------------------------
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # --------------------------------------------------
    # UPDATE (PUT)
    # --------------------------------------------------
    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=False,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    # --------------------------------------------------
    # PARTIAL UPDATE (PATCH) ✅ FIX
    # --------------------------------------------------
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True,   # 🔥 REQUIRED FOR PATCH
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    # --------------------------------------------------
    # DELETE (SOFT DELETE)
    # --------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name

        instance.soft_delete()
        instance.deleted_by = request.user
        instance.save(update_fields=['deleted_by'])

        return Response(
            {'success': True, 'message': f'Bot calling provider "{name}" deleted successfully'},
            status=status.HTTP_204_NO_CONTENT,
        )

    # --------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------
    @action(detail=True, methods=['post'], url_path='health_check')
    def health_check(self, request, pk=None):
        provider = self.get_object()
        service = BotCallingProviderService()

        result = service.check_provider_health(provider, user=request.user)

        return Response(
            {
                "provider_id": provider.id,
                "provider_name": provider.name,
                "provider_type": provider.provider_type,
                "is_healthy": result.get("success"),
                "status": result.get("status"),
                "details": result.get("details"),
                "response_time": result.get("response_time"),
                "last_health_check": provider.last_health_check,
            },
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------
    # RESET USAGE
    # --------------------------------------------------
    @action(detail=True, methods=['post'])
    def reset_usage(self, request, pk=None):
        provider = self.get_object()
        reset_type = request.data.get('type', 'daily')

        if reset_type == 'daily':
            provider.reset_daily_usage()
        elif reset_type == 'monthly':
            provider.reset_monthly_usage()
        else:
            return Response(
                {'error': 'Invalid reset type. Use "daily" or "monthly"'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'message': f'{reset_type.title()} bot call usage reset successfully'})

    # --------------------------------------------------
    # SET DEFAULT
    # --------------------------------------------------
    @action(detail=True, methods=['patch'], url_path='set-default')
    def set_default(self, request, pk=None):
        provider = self.get_object()

        BotCallingProviderConfig.objects.filter(is_deleted=False).update(is_default=False)

        provider.is_default = True
        provider.is_active = True
        provider.save(update_fields=['is_default', 'is_active'])

        return Response(
            {"message": "Default provider set successfully", "provider_id": provider.id},
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------
    # ACTIVATE / DEACTIVATE
    # --------------------------------------------------
    @action(detail=True, methods=['patch'], url_path='activate')
    def activate(self, request, pk=None):
        provider = self.get_object()
        provider.is_active = True
        provider.save(update_fields=['is_active'])

        return Response(
            {"message": "Provider activated successfully", "provider_id": provider.id},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['patch'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        provider = self.get_object()
        provider.is_active = False
        provider.save(update_fields=['is_active'])

        return Response(
            {"message": "Provider deactivated successfully", "provider_id": provider.id},
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------
    # STATISTICS
    # --------------------------------------------------
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        providers = self.get_queryset()
        stats = []

        for provider in providers:
            daily_pct = (provider.calls_made_today / provider.daily_limit * 100) if provider.daily_limit else 0
            monthly_pct = (provider.calls_made_this_month / provider.monthly_limit * 100) if provider.monthly_limit else 0

            recent_logs = BotCallingProviderUsageLog.objects.filter(
                provider=provider,
                logged_at__gte=timezone.now() - timedelta(days=7),
            )

            total_calls = sum(l.calls_made for l in recent_logs)
            total_success = sum(l.success_count for l in recent_logs)
            total_response_time = sum(l.total_response_time for l in recent_logs)

            success_rate = (total_success / total_calls * 100) if total_calls else 0
            avg_response_time = (total_response_time / total_success) if total_success else 0

            stats.append({
                'provider_id': provider.id,
                'provider_name': provider.name,
                'provider_type': provider.provider_type,
                'is_active': provider.is_active,
                'status': provider.status,
                'calls_made_today': provider.calls_made_today,
                'calls_made_this_month': provider.calls_made_this_month,
                'daily_limit': provider.daily_limit,
                'monthly_limit': provider.monthly_limit,
                'daily_usage_percentage': round(daily_pct, 2),
                'monthly_usage_percentage': round(monthly_pct, 2),
                'last_health_check': provider.last_health_check,
                'success_rate': round(success_rate, 2),
                'average_response_time': round(avg_response_time, 3),
            })

        serializer = BotCallingProviderStatsSerializer(stats, many=True)
        return Response(serializer.data)

    # --------------------------------------------------
    # HEALTH STATUS FOR ALL
    # --------------------------------------------------
    @action(detail=False, methods=['get'])
    def health_status(self, request):
        providers = self.get_queryset()
        service = BotCallingProviderService()

        data = []
        for provider in providers:
            result = service.check_provider_health(provider, user=request.user)
            data.append({
                "provider_id": provider.id,
                "provider_name": provider.name,
                "provider_type": provider.provider_type,
                "status": result.get("status"),
                "details": result.get("details"),
                "is_healthy": result.get("success"),
                "last_health_check": provider.last_health_check,
                "can_make_call": provider.can_make_call(),
            })

        return Response(data)


# ============================================================
#  HEALTH LOG VIEWSET
# ============================================================

class BotCallingProviderHealthLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BotCallingProviderHealthLog.objects.all()
    serializer_class = BotCallingProviderHealthLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)

        is_healthy = self.request.query_params.get('is_healthy')
        if is_healthy is not None:
            queryset = queryset.filter(is_healthy=is_healthy.lower() == 'true')

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(checked_at__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(checked_at__lte=end_date)

        return queryset.order_by('-checked_at')


# ============================================================
#  USAGE LOG VIEWSET
# ============================================================

class BotCallingProviderUsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BotCallingProviderUsageLog.objects.all()
    serializer_class = BotCallingProviderUsageLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(logged_at__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(logged_at__lte=end_date)

        return queryset.order_by('-logged_at')


# ============================================================
#  TEST RESULT VIEWSET
# ============================================================

class BotCallingProviderTestResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BotCallingProviderTestResult.objects.all()
    serializer_class = BotCallingProviderTestResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        test_number = self.request.query_params.get('test_number')
        if test_number:
            queryset = queryset.filter(test_number__icontains=test_number)

        return queryset.order_by('-tested_at')
