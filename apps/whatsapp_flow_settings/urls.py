from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppConfigurationViewSet, 
    WhatsAppAccessPermissionViewSet, 
    FlowAccessRoleViewSet, 
    FlowAuditLogViewSet
)

router = DefaultRouter()
router.register(r'permissions', WhatsAppAccessPermissionViewSet, basename='permissions')
router.register(r'roles', FlowAccessRoleViewSet, basename='roles')
router.register(r'auditlogs', FlowAuditLogViewSet, basename='auditlogs')

urlpatterns = [
    path('settings/', WhatsAppConfigurationViewSet.as_view({
        'get': 'list',             
        'post': 'create',          
        'patch': 'update_singleton'
    })),

    path('', include(router.urls)),
]