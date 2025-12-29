from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegionViewSet, StateViewSet, BranchViewSet, 
    DepartmentViewSet, TeamViewSet, HierarchySummaryView
)

router = DefaultRouter()
router.register(r'regions', RegionViewSet)
router.register(r'states', StateViewSet)
router.register(r'branches', BranchViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'teams', TeamViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('summary/', HierarchySummaryView.as_view()), # API for the Table
]