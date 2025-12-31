from rest_framework.routers import DefaultRouter
from .views import ClientViewSet

router = DefaultRouter()
router.register(r"", ClientViewSet, basename="clients")

urlpatterns = router.urls
