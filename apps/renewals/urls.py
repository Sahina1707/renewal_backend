from rest_framework.routers import DefaultRouter
from .views import CompetitorViewSet, RenewalCaseViewSet

router = DefaultRouter()
router.register(r'competitors', CompetitorViewSet, basename='competitor')
router.register(r'cases', RenewalCaseViewSet, basename='renewal-cases')

urlpatterns = router.urls
