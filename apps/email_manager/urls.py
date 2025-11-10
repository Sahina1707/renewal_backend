from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmailManagerViewSet

router = DefaultRouter()
# router.register(r'email-manager', EmailManagerViewSet, basename='email-manager')
router.register(r'', EmailManagerViewSet, basename='email-manager')


urlpatterns = [
    path('', include(router.urls)),
]

