from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AudienceViewSet, AudienceContactViewSet

app_name = 'audience_manager'

router = DefaultRouter()
# /api/audience/audiences/
router.register(r'audiences', AudienceViewSet, basename='audience')
# /api/audience/contacts/ (Can be used for global search/management)
router.register(r'contacts', AudienceContactViewSet, basename='audience-contact')

urlpatterns = [
    path('', include(router.urls)),
]