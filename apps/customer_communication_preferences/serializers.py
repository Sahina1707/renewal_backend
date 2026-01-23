from rest_framework import serializers
from .models import CustomerCommunicationPreference
from apps.customers.models import Customer


class CustomerCommunicationPreferenceSerializer(serializers.ModelSerializer):
    """Base serializer for Customer Communication Preferences"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    communication_summary = serializers.CharField(read_only=True)
    is_contactable = serializers.BooleanField(read_only=True)
    enabled_channels = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerCommunicationPreference
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'preferred_channel',
            'secondary_channel',
            'communication_type',
            'frequency',
            'email_enabled',
            'sms_enabled',
            'phone_enabled',
            'whatsapp_enabled',
            'postal_mail_enabled',
            'push_notification_enabled',
            'preferred_time',
            'preferred_language',
            'alternate_email',
            'alternate_phone',
            'do_not_disturb',
            'dnd_start_time',
            'dnd_end_time',
            'marketing_consent',
            'data_sharing_consent',
            'is_active',
            'priority_level',
            'notes',
            'communication_summary',
            'is_contactable',
            'enabled_channels',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_enabled_channels(self, obj):
        """Get list of enabled communication channels"""
        return obj.get_enabled_channels()


class CustomerCommunicationPreferenceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Customer Communication Preferences"""
    
    class Meta:
        model = CustomerCommunicationPreference
        fields = [
            'customer',
            'preferred_channel',
            'secondary_channel',
            'communication_type',
            'frequency',
            'email_enabled',
            'sms_enabled',
            'phone_enabled',
            'whatsapp_enabled',
            'postal_mail_enabled',
            'push_notification_enabled',
            'preferred_time',
            'preferred_language',
            'alternate_email',
            'alternate_phone',
            'do_not_disturb',
            'dnd_start_time',
            'dnd_end_time',
            'marketing_consent',
            'data_sharing_consent',
            'is_active',
            'priority_level',
            'notes',
        ]
    
    def validate_customer(self, value):
        """Validate that customer exists"""
        if not Customer.objects.filter(id=value.id, is_deleted=False).exists():
            raise serializers.ValidationError("Customer does not exist or has been deleted.")
        return value
    
    def validate(self, data):
        """Custom validation for communication preferences"""
        customer = data.get('customer')
        communication_type = data.get('communication_type')
        
        if customer and communication_type:
            existing_preference = CustomerCommunicationPreference.objects.filter(
                customer=customer,
                communication_type=communication_type,
                is_deleted=False
            ).exists()
            
            if existing_preference:
                raise serializers.ValidationError(
                    f"Communication preference for {communication_type} already exists for this customer."
                )
        
        # Validate DND time settings
        dnd_start = data.get('dnd_start_time')
        dnd_end = data.get('dnd_end_time')
        
        if data.get('do_not_disturb') and (not dnd_start or not dnd_end):
            raise serializers.ValidationError(
                "DND start and end times are required when do not disturb is enabled."
            )
        
        # Validate at least one channel is enabled
        channels_enabled = any([
            data.get('email_enabled', False),
            data.get('sms_enabled', False),
            data.get('phone_enabled', False),
            data.get('whatsapp_enabled', False),
            data.get('postal_mail_enabled', False),
            data.get('push_notification_enabled', False),
        ])
        
        if not channels_enabled:
            raise serializers.ValidationError(
                "At least one communication channel must be enabled."
            )
        
        return data


class CustomerCommunicationPreferenceListSerializer(serializers.ModelSerializer):
    """Serializer for listing Customer Communication Preferences"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    communication_summary = serializers.CharField(read_only=True)
    is_contactable = serializers.BooleanField(read_only=True)
    preferred_channel_display = serializers.CharField(source='get_preferred_channel_display', read_only=True)
    communication_type_display = serializers.CharField(source='get_communication_type_display', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    preferred_time_display = serializers.CharField(source='get_preferred_time_display', read_only=True)
    
    class Meta:
        model = CustomerCommunicationPreference
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'customer_email',
            'customer_phone',
            'preferred_channel',
            'preferred_channel_display',
            'communication_type',
            'communication_type_display',
            'frequency',
            'frequency_display',
            'preferred_time',
            'preferred_time_display',
            'preferred_language',
            'email_enabled',
            'sms_enabled',
            'phone_enabled',
            'whatsapp_enabled',
            'do_not_disturb',
            'marketing_consent',
            'is_active',
            'priority_level',
            'communication_summary',
            'is_contactable',
            'created_at',
            'updated_at',
        ]


class CustomerCommunicationPreferenceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Customer Communication Preferences"""
    
    class Meta:
        model = CustomerCommunicationPreference
        fields = [
            'preferred_channel',
            'secondary_channel',
            'frequency',
            'email_enabled',
            'sms_enabled',
            'phone_enabled',
            'whatsapp_enabled',
            'postal_mail_enabled',
            'push_notification_enabled',
            'preferred_time',
            'preferred_language',
            'alternate_email',
            'alternate_phone',
            'do_not_disturb',
            'dnd_start_time',
            'dnd_end_time',
            'marketing_consent',
            'data_sharing_consent',
            'is_active',
            'priority_level',
            'notes',
        ]
    
    def validate(self, data):
        """Custom validation for updating communication preferences"""
        # Validate DND time settings
        dnd_start = data.get('dnd_start_time')
        dnd_end = data.get('dnd_end_time')
        do_not_disturb = data.get('do_not_disturb', self.instance.do_not_disturb)
        
        if do_not_disturb and (not dnd_start or not dnd_end):
            if not self.instance.dnd_start_time or not self.instance.dnd_end_time:
                raise serializers.ValidationError(
                    "DND start and end times are required when do not disturb is enabled."
                )
        
        # Validate at least one channel is enabled
        channels_enabled = any([
            data.get('email_enabled', self.instance.email_enabled),
            data.get('sms_enabled', self.instance.sms_enabled),
            data.get('phone_enabled', self.instance.phone_enabled),
            data.get('whatsapp_enabled', self.instance.whatsapp_enabled),
            data.get('postal_mail_enabled', self.instance.postal_mail_enabled),
            data.get('push_notification_enabled', self.instance.push_notification_enabled),
        ])
        
        if not channels_enabled:
            raise serializers.ValidationError(
                "At least one communication channel must be enabled."
            )
        
        return data
