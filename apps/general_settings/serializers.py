from rest_framework import serializers
from .models import UserSettings

class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            'user',
            'dark_mode',
            'language',
            'time_zone',
            'email_notifications',
            'sms_notifications',
            'mfa_enabled',
        ]
        read_only_fields = ['user']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {
            'user': data.get('user'),
            'appearance': {
                'dark_mode': data.get('dark_mode')
            },
            'regional_settings': {
                'language': data.get('language'),
                'time_zone': data.get('time_zone')
            },
            'notifications': {
                'email_notifications': data.get('email_notifications'),
                'sms_notifications': data.get('sms_notifications')
            },
            'multi_factor_authentication': {
                'mfa_enabled': data.get('mfa_enabled')
            }
        }