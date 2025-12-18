from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CallProviderConfigViewSet,
    CallProviderHealthLogViewSet,
    CallProviderUsageLogViewSet,
    CallProviderTestResultViewSet,
)
from .webhook_views import (
    TwilioStatusCallbackView,
    ExotelStatusCallbackView,
    UbonaStatusCallbackView,
)

router = DefaultRouter()
router.register(r'providers', CallProviderConfigViewSet, basename='call-provider')
router.register(r'health-logs', CallProviderHealthLogViewSet, basename='call-provider-health-logs')
router.register(r'usage-logs', CallProviderUsageLogViewSet, basename='call-provider-usage-logs')
router.register(r'test-results', CallProviderTestResultViewSet, basename='call-provider-test-results')

urlpatterns = [
    path(
        "twilio/status-callback/<int:provider_id>/",
        TwilioStatusCallbackView.as_view(),
        name="twilio-call-status-callback",
    ),
    path(
        "exotel/status-callback/<int:provider_id>/",
        ExotelStatusCallbackView.as_view(),
        name="exotel-call-status-callback",
    ),
    path(
        "ubona/status-callback/<int:provider_id>/",
        UbonaStatusCallbackView.as_view(),
        name="ubona-call-status-callback",
    ),
]

urlpatterns += router.urls
