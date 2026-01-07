from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FeedbackDashboardView, 
    CampaignViewSet, 
    SubmissionViewSet, 
    SurveyViewSet,
    PublicSurveyViewSet,
    FeedbackAnalyticsView,
    DistributionChannelViewSet,
    PublicSurveyView,
    ResponseListViewSet,
    AudienceViewSet,
    AutomationViewSet,
)

router = DefaultRouter()
router.register(r'surveys', SurveyViewSet, basename='surveys')
router.register(r'campaigns', CampaignViewSet, basename='campaigns')
router.register(r'inbox', SubmissionViewSet, basename='inbox')
router.register(r'builder', SurveyViewSet, basename='builder')
router.register(r'channels', DistributionChannelViewSet, basename='channels')
router.register(r'responses', ResponseListViewSet, basename='response')
router.register(r'audiences', AudienceViewSet, basename='audience')
router.register(r'automation', AutomationViewSet, basename='automation')

urlpatterns = [
    path('dashboard-stats/', FeedbackDashboardView.as_view(), name='dashboard-stats'),
    path('analytics/', FeedbackAnalyticsView.as_view(), name='analytics'), 
    path('public/<int:survey_id>/', PublicSurveyView.as_view(), name='public_survey'), 
    path('', include(router.urls)),
]