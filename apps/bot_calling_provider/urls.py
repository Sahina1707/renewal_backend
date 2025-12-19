from rest_framework.routers import DefaultRouter

from .views import (
    BotCallingProviderConfigViewSet,
    BotCallingProviderHealthLogViewSet,
    BotCallingProviderUsageLogViewSet,
    BotCallingProviderTestResultViewSet,
)

router = DefaultRouter()
router.register(r'providers', BotCallingProviderConfigViewSet, basename='bot-calling-provider')
router.register(r'health-logs', BotCallingProviderHealthLogViewSet, basename='bot-calling-provider-health-logs')
router.register(r'usage-logs', BotCallingProviderUsageLogViewSet, basename='bot-calling-provider-usage-logs')
router.register(r'test-results', BotCallingProviderTestResultViewSet, basename='bot-calling-provider-test-results')

urlpatterns = router.urls
