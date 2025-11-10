from rest_framework import serializers
from .models import EmailManager
from apps.templates.models import Template


class EmailManagerSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = EmailManager
        fields = [
            'id',
            'to',
            'cc',
            'bcc',
            'subject',
            'message',
            'policy_number',
            'customer_name',
            'renewal_date',
            'premium_amount',
            'priority',
            'schedule_send',
            'schedule_date_time',
            'track_opens',
            'track_clicks',
            'template_id',
            'email_status',
            'sent_at',
            'error_message',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at', 'email_status', 'sent_at', 'error_message']


class EmailManagerCreateSerializer(serializers.ModelSerializer):
    templates_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = EmailManager
        fields = [
            'to',
            'cc',
            'bcc',
            'subject',
            'message',
            'policy_number',
            'customer_name',
            'renewal_date',
            'premium_amount',
            'priority',
            'schedule_send',
            'schedule_date_time',
            'track_opens',
            'track_clicks',
            'templates_id',
        ]
    
    def validate_schedule_date_time(self, value):
        if self.initial_data.get('schedule_send') and not value:
            raise serializers.ValidationError(
                "Schedule date and time must be provided when schedule_send is True."
            )
        return value
    
    def validate_templates_id(self, value):
        if value is not None:
            if isinstance(value, Template):
                value = value.id
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise serializers.ValidationError("templates_id must be a valid integer.")
            
            try:
                Template.objects.get(id=value)
            except Template.DoesNotExist:
                raise serializers.ValidationError(f"Template with ID {value} does not exist.")
        return value
    
    def validate(self, data):
        if data.get('schedule_send') and not data.get('schedule_date_time'):
            raise serializers.ValidationError({
                'schedule_date_time': 'Schedule date and time is required when schedule_send is True.'
            })
        return data
    
    def create(self, validated_data):
        template_pk = validated_data.pop('templates_id', None)
        if template_pk is not None:
            validated_data['template_id'] = template_pk
            
        return super().create(validated_data)


class EmailManagerUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = EmailManager
        fields = [
            'to',
            'cc',
            'bcc',
            'subject',
            'message',
            'policy_number',
            'customer_name',
            'renewal_date',
            'premium_amount',
            'priority',
            'schedule_send',
            'schedule_date_time',
            'track_opens',
            'track_clicks',
            'templates_id',
        ]
    
    def validate_schedule_date_time(self, value):
        schedule_send = self.initial_data.get('schedule_send')
        if schedule_send and not value:
            if self.instance:
                if self.instance.schedule_send and not value:
                    raise serializers.ValidationError(
                        "Schedule date and time must be provided when schedule_send is True."
                    )
        return value
    
    def validate(self, data):
        schedule_send = data.get('schedule_send', self.instance.schedule_send if self.instance else False)
        schedule_date_time = data.get('schedule_date_time', self.instance.schedule_date_time if self.instance else None)
        
        if schedule_send and not schedule_date_time:
            raise serializers.ValidationError({
                'schedule_date_time': 'Schedule date and time is required when schedule_send is True.'
            })
        return data

