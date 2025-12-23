from rest_framework import serializers
# Make sure these imports are correct based on your project structure
from apps.whatsapp_flow_management.models import WhatsAppMessageTemplate, WhatsAppFlow
from .models import WhatsAppConfiguration, WhatsAppAccessPermission, FlowAccessRole, FlowAuditLog

class FlowAccessRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowAccessRole
        fields = ['id', 'name', 'description', 'can_publish', 'can_edit'] 

class WhatsAppAccessPermissionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role_details = FlowAccessRoleSerializer(source='role', read_only=True)

    class Meta:
        model = WhatsAppAccessPermission
        fields = ['id', 'user', 'username', 'email', 'role', 'role_details'] 

class FlowAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    action_display = serializers.CharField(source='get_action_type_display', read_only=True)

    class Meta:
        model = FlowAuditLog
        fields = ['id', 'timestamp', 'actor_name', 'action_type', 'action_display', 'details']

class WhatsAppConfigurationSerializer(serializers.ModelSerializer):
    # Field definitions...
    whatsapp_api_settings = serializers.SerializerMethodField()
    flow_builder_settings = serializers.SerializerMethodField()
    business_hours_settings = serializers.SerializerMethodField()
    message_settings = serializers.SerializerMethodField()
    rate_limiting = serializers.SerializerMethodField()
    integration_status = serializers.SerializerMethodField()
    flow_access_permissions = serializers.SerializerMethodField()
    flow_activity_logs = serializers.SerializerMethodField()
    
    class Meta:
        model = WhatsAppConfiguration
        fields = [
            'phone_number_id', 'access_token', 'webhook_url', 'verify_token',
            'is_enabled', 'enable_business_hours', 'business_start_time',
            'business_end_time', 'timezone', 'fallback_message', 'max_retries',
            'retry_delay', 'enable_rate_limiting', 'messages_per_minute',
            'messages_per_hour', 'enable_visual_flow_builder',
            'enable_message_templates', 'enable_auto_response',
            'enable_analytics_and_reports',
            # Nested Objects
            'whatsapp_api_settings',
            'flow_builder_settings',
            'business_hours_settings',
            'message_settings',
            'rate_limiting',
            'integration_status',     # <--- This will now contain the dynamic data
            'flow_access_permissions',
            'flow_activity_logs',
        ]
        read_only_fields = ['whatsapp_api_settings', 'integration_status', 'flow_activity_logs']

    # --- Helper Methods for Logic (Reused) ---

    def _get_template_status_data(self):
        """Helper to get template status logic"""
        pending_count = WhatsAppMessageTemplate.objects.filter(status='PENDING').count()
        if pending_count > 0:
            return {'status': f"{pending_count} templates pending approval"}
        return {'status': "All templates approved"}

    def _get_flow_status_data(self):
        """Helper to get flow status logic"""
        active_flows = WhatsAppFlow.objects.filter(status='PUBLISHED').count()
        draft_flows = WhatsAppFlow.objects.filter(status='DRAFT').count()
        
        if active_flows > 0:
            return {'status': f"{active_flows} Active Flows running"}
        elif draft_flows > 0:
            return {'status': "Draft flows in progress"}
        else:
            return {'status': "Ready to create flows"}

    # --- Main Serializer Methods ---

    def get_whatsapp_api_settings(self, obj):
        return {
            'phone_number_id': obj.phone_number_id,
            'webhook_url': obj.webhook_url,
            'is_enabled': obj.is_enabled,
        }

    def get_business_hours_settings(self, obj):
        return {
            'enable_business_hours': obj.enable_business_hours,
            'business_start_time': obj.business_start_time,
            'business_end_time': obj.business_end_time,
            'timezone': obj.timezone,
        }

    def get_message_settings(self, obj):
        return {
            'fallback_message': obj.fallback_message,
            'max_retries': obj.max_retries,
            'retry_delay': obj.retry_delay
        }

    def get_rate_limiting(self, obj):
        return {
            'enable_rate_limiting': obj.enable_rate_limiting,
            'messages_per_minute': obj.messages_per_minute,
            'messages_per_hour': obj.messages_per_hour,
        }

    # --- UPDATED INTEGRATION STATUS ---
    def get_integration_status(self, obj):
        # 1. Reuse the logic for Templates and Flows
        template_data = self._get_template_status_data()
        flow_data = self._get_flow_status_data()

        return {
            'whatsapp_api': {
                'status': 'Connected and Verified' if obj.phone_number_id else 'Not Configured'
            },
            'webhook_configuration': {
                'status': 'Active' if obj.webhook_url and obj.is_enabled else 'Inactive'
            },
            # 2. Inject Dynamic Data Here
            'message_templates': template_data,
            'flow_builder': flow_data
        }

    def get_flow_builder_settings(self, obj):
        # This returns settings toggles, not status
        return {
            'enable_visual_flow_builder': obj.enable_visual_flow_builder,
            'enable_message_templates': obj.enable_message_templates,
        }

    def get_flow_access_permissions(self, obj):
        qs = WhatsAppAccessPermission.objects.select_related('user', 'role').all()
        return WhatsAppAccessPermissionSerializer(qs, many=True).data

    def get_flow_activity_logs(self, obj):
        qs = FlowAuditLog.objects.select_related('actor').order_by('-timestamp')[:5] 
        return FlowAuditLogSerializer(qs, many=True).data