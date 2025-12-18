from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from .models import WhatsAppConfiguration, WhatsAppAccessPermission, FlowAccessRole, FlowAuditLog 
from .serializers import (
    WhatsAppConfigurationSerializer, WhatsAppAccessPermissionSerializer,
    FlowAuditLogSerializer, FlowAccessRoleSerializer 
)
from rest_framework.decorators import action


class WhatsAppConfigurationViewSet(viewsets.ViewSet):
    """
    Unified API for the Settings Page (Handles Global Config + Bulk Permissions Update).
    """
    permission_classes = [permissions.AllowAny] 
    def get_object(self):
        config = WhatsAppConfiguration.objects.first()
        if not config:
            config = WhatsAppConfiguration.objects.create()
        return config

    def list(self, request):
        config = self.get_object()
        serializer = WhatsAppConfigurationSerializer(config)
        return Response(serializer.data)

    def update(self, request):
        """
        POST/PATCH /settings/
        Handles updating WhatsAppConfiguration fields AND bulk permissions update.
        """
        config = self.get_object()
        data = request.data.copy()  # Make a mutable copy to safely delete fields
        
        if 'flow_access_permissions' in data:
            # PASS THE REQUEST OBJECT TO GET USER INFO FOR AUDIT LOGGING
            self._update_permissions(data['flow_access_permissions'], request)
            # Remove permissions from data so the main serializer doesn't complain
            del data['flow_access_permissions']

    # views.py

# ... (WhatsAppConfigurationViewSet definition)

    def _update_permissions(self, new_permissions_data, request): # <-- ADDED request argument
        """
        Performs a full sync of permissions: creates new, updates existing, deletes missing.
        """
        existing_permissions = {p.id: p for p in WhatsAppAccessPermission.objects.all()}
        permissions_to_keep = set()
        permissions_updated = 0
        permissions_created = 0

        try:
            with transaction.atomic():
                for item in new_permissions_data:
                    permission_id = item.get('id')
                    user_id = item.get('user')
                    role_id = item.get('role')

                    if permission_id in existing_permissions:
                        permission = existing_permissions[permission_id]
                        if role_id is not None and permission.role_id != role_id:
                            permission.role_id = role_id
                            permission.save()
                            permissions_updated += 1 # Track updates
                        permissions_to_keep.add(permission_id)

                    elif user_id is not None and role_id is not None:
                        # Use update_or_create to handle cases where an existing user permission 
                        # might be submitted without an ID if the front-end treats it as new.
                        permission, created = WhatsAppAccessPermission.objects.update_or_create(
                            user_id=user_id,
                            defaults={'role_id': role_id},
                        )
                        if created:
                            permissions_created += 1 # Track creations
                        else:
                            permissions_updated += 1
                            
                        permissions_to_keep.add(permission.id)
                        
                # --- Delete Missing (Soft Delete) ---
                ids_to_delete = set(existing_permissions.keys()) - permissions_to_keep
                WhatsAppAccessPermission.objects.filter(id__in=ids_to_delete).update(is_deleted=True)
                
                # --- Audit Log Changes ---
                log_details = f"Permissions updated: {permissions_updated} modified, {permissions_created} created, {len(ids_to_delete)} soft-deleted."
                
                # Use request.user if available. Since it's AllowAny, we might need a fallback.
                actor = request.user if request.user.is_authenticated else None
                
                FlowAuditLog.objects.create(
                    actor=actor, 
                    action_type='USER_CHANGE', 
                    details=log_details
                )


        except IntegrityError as e:
            raise serializers.ValidationError({"permissions": "Database integrity error: Check if user or role IDs are valid."})
        except Exception as e:
            raise serializers.ValidationError({"permissions": f"Error updating permissions: {str(e)}"})

    @action(detail=False, methods=['post'])
    def save_all_settings(self, request):
        return self.update(request)
class WhatsAppAccessPermissionViewSet(viewsets.ModelViewSet):
    queryset = WhatsAppAccessPermission.objects.select_related('user', 'role').all()
    serializer_class = WhatsAppAccessPermissionSerializer
    permission_classes = [permissions.AllowAny]
    
    # We explicitly remove methods to enforce update via the single /settings/ endpoint
    def create(self, request, *args, **kwargs):
        return Response({"detail": "Operation not allowed. Use /settings/ for bulk creation."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def retrieve(self, request, *args, **kwargs):
        return Response({"detail": "Operation not allowed. Use /settings/ for bulk retrieval."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def update(self, request, *args, **kwargs):
        return Response({"detail": "Operation not allowed. Use /settings/ for bulk update."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        
    def partial_update(self, request, *args, **kwargs):
        return Response({"detail": "Operation not allowed. Use /settings/ for bulk update."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        
    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Operation not allowed. Use /settings/ for bulk delete."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
class FlowAccessRoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API to fetch the available roles for the permissions dropdown.
    """
    queryset = FlowAccessRole.objects.all()
    serializer_class = FlowAccessRoleSerializer 
    permission_classes = [permissions.AllowAny]
    
class FlowAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for the full audit log history.
    """
    queryset = FlowAuditLog.objects.select_related('actor').order_by('-timestamp').all()
    serializer_class = FlowAuditLogSerializer
    permission_classes = [permissions.AllowAny]