from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SurveySettingsViewSet, IntegrationViewSet

router = DefaultRouter()
router.register(r'config', SurveySettingsViewSet, basename='settings')
router.register(r'integrations', IntegrationViewSet, basename='integrations')

urlpatterns = [
    path('', include(router.urls)),
]