from rest_framework.routers import DefaultRouter
from .views import EmailManagerViewSet
from .views import EmailManagerInboxViewSet

router = DefaultRouter()
router.register(r'', EmailManagerViewSet, basename='email-manager')
router.register(r'', EmailManagerInboxViewSet, basename='email-manager-inbox')

urlpatterns = router.urls
