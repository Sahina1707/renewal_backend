from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DNCSettingsView,
    DNCRegistryViewSet,
    DNCOverrideView,
    DNCStatisticsView,
    BulkUploadView,
    DNCEvaluateView,  
)

router = DefaultRouter()
router.register(r'registry', DNCRegistryViewSet, basename='registry')

urlpatterns = [
    path('settings/', DNCSettingsView.as_view(), name='dnc-settings'),
    path('', include(router.urls)),
    path('override/', DNCOverrideView.as_view(), name='dnc-override'),
    path('evaluate/', DNCEvaluateView.as_view(), name='dnc-evaluate'), 
    path('statistics/', DNCStatisticsView.as_view(), name='dnc-statistics'),
    path('upload/', BulkUploadView.as_view(), name='dnc-upload'),
]
