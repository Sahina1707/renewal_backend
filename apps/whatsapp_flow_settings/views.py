from rest_framework import viewsets, permissions, status, serializers
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from .models import WhatsAppConfiguration, WhatsAppAccessPermission, FlowAccessRole, FlowAuditLog 
from .serializers import (
    WhatsAppConfigurationSerializer, WhatsAppAccessPermissionSerializer,
    FlowAuditLogSerializer, FlowAccessRoleSerializer 
)
from rest_framework.decorators import action

class AuditModelViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that automatically fills created_by and updated_by
    from the logged-in user (request.user).
    """
    def perform_create(self, serializer):
        # When creating, set both created_by and updated_by
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # When updating, only change updated_by
        serializer.save(updated_by=self.request.user)
                        
class WhatsAppConfigurationViewSet(AuditModelViewSet):
    queryset = WhatsAppConfiguration.objects.all()
    serializer_class = WhatsAppConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]

    # 1. GET /settings/ (Returns the single object)
    def list(self, request, *args, **kwargs):
        config = WhatsAppConfiguration.objects.first()
        if config:
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        return Response({"detail": "No configuration found. Please create one (POST)."}, status=status.HTTP_404_NOT_FOUND)

    # 2. POST /settings/ (Creates the single object)
    def create(self, request, *args, **kwargs):
        if WhatsAppConfiguration.objects.exists():
            return Response({"detail": "Configuration already exists. Use PATCH."}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

    # 3. PATCH /settings/ (Updates the single object WITHOUT an ID)
    # This is the special method to match your Postman "update_all"
    def update_singleton(self, request, *args, **kwargs):
        instance = WhatsAppConfiguration.objects.first()
        if not instance:
            return Response({"detail": "No configuration found."}, status=status.HTTP_404_NOT_FOUND)

        # Call the standard update logic with this instance
        kwargs['pk'] = instance.pk 
        return self.update(request, *args, **kwargs)

    # 4. The Standard Update Logic (Fixed with Transaction)
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        # If called from update_singleton, we get the instance via get_object() using the PK we injected
        instance = self.get_object()
        data = request.data.copy()

        # A. Handle Permissions
        if 'flow_access_permissions' in data:
            self._update_permissions(data['flow_access_permissions'], request)
            del data['flow_access_permissions']

        # B. Handle Standard Fields
        serializer = self.get_serializer(instance, data=data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def perform_update(self, serializer):
        instance = serializer.instance
        changes = []
        
        # Check for changes in validated_data
        for field, new_value in serializer.validated_data.items():
            old_value = getattr(instance, field)
            if old_value != new_value:
                field_verbose = instance._meta.get_field(field).verbose_name
                changes.append(f"{field_verbose}: {old_value} -> {new_value}")
        
        super().perform_update(serializer)
        
        if changes:
            FlowAuditLog.objects.create(
                actor=self.request.user,
                action_type='EDIT',
                details="Configuration updated: " + "; ".join(changes)
            )
      
    def _update_permissions(self, new_permissions_data, request): 
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
                        
                ids_to_delete = set(existing_permissions.keys()) - permissions_to_keep
                WhatsAppAccessPermission.objects.filter(id__in=ids_to_delete).update(is_deleted=True)                
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

    @action(detail=False, methods=['post'])
    def reset_defaults(self, request):
        config = WhatsAppConfiguration.objects.first()
        if not config:
            return Response({"detail": "No configuration found."}, status=status.HTTP_404_NOT_FOUND)
            
        # Reset fields to defaults (excluding API credentials)
        config.is_enabled = True
        config.enable_business_hours = True
        config.business_start_time = "09:00"
        config.business_end_time = "18:00"
        config.timezone = 'Asia/Kolkata'
        config.fallback_message = "Thank you for your message. We will get back to you soon."
        config.max_retries = 3
        config.retry_delay = 300
        config.enable_rate_limiting = True
        config.messages_per_minute = 60
        config.messages_per_hour = 1000
        config.enable_visual_flow_builder = True
        config.enable_message_templates = True
        config.enable_auto_response = True
        config.enable_analytics_and_reports = True
        
        config.updated_by = request.user
        config.save()
        
        FlowAuditLog.objects.create(
            actor=request.user, 
            action_type='EDIT', 
            details="System settings reset to defaults"
        )
        
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    
class WhatsAppAccessPermissionViewSet(AuditModelViewSet):
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

    @action(detail=False, methods=['get'])
    def available_users(self, request):
        User = get_user_model()
        # Get IDs of users who already have an active permission
        assigned_ids = WhatsAppAccessPermission.objects.filter(is_deleted=False).values_list('user_id', flat=True)
        
        # Filter users not in that list
        available = User.objects.exclude(id__in=assigned_ids).values('id', 'username', 'email')
        
        return Response(list(available))

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