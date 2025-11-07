from .views import (
    CampaignViewSet, EmailTrackingView, EmailClickTrackingView,
    get_all_campaigns, test_tracking_pixel, get_campaign_tracking_stats,
    update_campaign_status
)
from .schedule_interval_views import CampaignScheduleIntervalViewSet
from rest_framework.routers import DefaultRouter
from django.urls import path, include

router = DefaultRouter()
router.register(r'schedule-intervals', CampaignScheduleIntervalViewSet, basename='campaign-schedule-interval')
router.register(r'', CampaignViewSet, basename='campaign')

urlpatterns = [
    path('track-open/', EmailTrackingView.as_view(), name='track-email-open'),
    path('track-click/', EmailClickTrackingView.as_view(), name='track-email-click'),
    path('test-tracking/', test_tracking_pixel, name='test-tracking-pixel'),
    path('<int:campaign_id>/tracking-stats/', get_campaign_tracking_stats, name='campaign-tracking-stats'),
    path('list/', get_all_campaigns, name='get-all-campaigns'),
    path('update-status/<int:campaign_id>/', update_campaign_status, name='update-campaign-status'),
    path('<int:pk>/change-status/', CampaignViewSet.as_view({'post': 'change_status'}), name='campaign-change-status-standalone'),
    path('', include(router.urls)),
]
