# File: apps/campaign_manager/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'campaigns', views.CampaignViewSet, basename='campaign')
router.register(r'logs', views.CampaignLogViewSet, basename='log')

urlpatterns = [
    path('', include(router.urls)),
]