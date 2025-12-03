from rest_framework.routers import DefaultRouter
from .views import UserViewSet,RoleViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'roles', RoleViewSet)

urlpatterns = router.urls