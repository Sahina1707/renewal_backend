from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppConfigurationViewSet, 
    WhatsAppAccessPermissionViewSet, 
    FlowAccessRoleViewSet,     
    FlowAuditLogViewSet        
)

router = DefaultRouter()
router.register(r'settings', WhatsAppConfigurationViewSet, basename='whatsapp-settings')
router.register(r'permissions', WhatsAppAccessPermissionViewSet, basename='whatsapp-permissions')
router.register(r'roles', FlowAccessRoleViewSet, basename='whatsapp-roles')
router.register(r'auditlogs', FlowAuditLogViewSet, basename='whatsapp-auditlogs')


urlpatterns = [
    path('', include(router.urls)),
]