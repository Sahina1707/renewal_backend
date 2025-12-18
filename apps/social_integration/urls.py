from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SocialPlatformViewSet,
    SocialVerificationSettingsView,
    SocialVerificationTestView,
    SocialIntegrationStatisticsView,
)

router = DefaultRouter()
router.register(r'platforms', SocialPlatformViewSet, basename='platforms')

urlpatterns = [
    path("", include(router.urls)),
    path("settings/", SocialVerificationSettingsView.as_view(), name="social-settings"),
    path("test-verification/", SocialVerificationTestView.as_view(), name="test-verification"),
    path("statistics/", SocialIntegrationStatisticsView.as_view(), name="social-statistics"),
]
