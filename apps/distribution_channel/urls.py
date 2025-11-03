from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DistributionChannelViewSet

router = DefaultRouter()
router.register(r'distribution-channels', DistributionChannelViewSet, basename='distribution-channel')

app_name = 'distribution_channel'

urlpatterns = [
    path('', include(router.urls)),
]
