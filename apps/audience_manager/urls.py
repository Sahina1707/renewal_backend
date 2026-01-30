from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AudienceViewSet, AudienceContactViewSet

app_name = 'audience_manager'

router = DefaultRouter()
router.register(r'audiences', AudienceViewSet, basename='audience')
router.register(r'contacts', AudienceContactViewSet, basename='audience-contact')

urlpatterns = [
    path('', include(router.urls)),
]