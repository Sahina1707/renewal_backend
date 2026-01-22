from rest_framework import serializers
from .models import SurveySettings, IntegrationCredential

class SurveySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveySettings
        # We keep '__all__' here so the "Update" API (PATCH) still accepts flat inputs
        fields = '__all__'
        read_only_fields = ('owner', 'created_at', 'updated_at')

    def to_representation(self, instance):
        """
        Custom Output: We manually construct the JSON to hide 
        created_at, updated_at, deleted_at, and owner fields.
        """
        return {
            "id": instance.id,
            
            # Group 1: General
            "general_settings": {
                "default_language": instance.default_language,
                "data_retention_period": instance.data_retention_period,
                "auto_archive_responses": instance.auto_archive_responses,
            },

            # Group 2: Notifications
            "notifications": {
                "email_notifications": instance.email_notifications,
                "sms_alerts": instance.sms_alerts,
                "weekly_reports": instance.weekly_reports,
                "real_time_alerts": instance.real_time_alerts,
                "negative_feedback_threshold": instance.negative_feedback_threshold,
            },

            # Group 3: Automation
            "automation": {
                "auto_send_post_purchase": instance.auto_send_post_purchase,
                "follow_up_reminders": instance.follow_up_reminders,
                "smart_response_routing": instance.smart_response_routing,
            }
        }

class IntegrationCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationCredential
        fields = '__all__'
        read_only_fields = ('owner', 'created_at', 'updated_at')
        extra_kwargs = {
            'api_key': {'write_only': True}, 
        }

    def to_representation(self, instance):
        """
        Clean output for Integrations (Hiding base model fields)
        """
        data = super().to_representation(instance)
        return {
            "id": data['id'],
            "provider": data['provider'],
            "is_active": data['is_active'],
            "configuration": {
                "webhook_url": data['webhook_url'],
                "meta_data": data['meta_data']
            }
        }