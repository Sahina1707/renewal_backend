from rest_framework import serializers
import re
import html
from .models import EmailManager
from apps.templates.models import Template
from apps.customer_payment_schedule.models import PaymentSchedule
from .models import EmailManagerInbox
from django.utils.html import strip_tags
from .models import EmailReply
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
            'template',
            'email_status',
            'sent_at',
            'error_message',
            'message_id',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at', 'email_status', 'sent_at', 'error_message', 'message_id']


class EmailManagerCreateSerializer(serializers.ModelSerializer):
    template = serializers.PrimaryKeyRelatedField(
        queryset=Template.objects.all(),
        required=False,
        allow_null=True
    )

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
            'template',
        ]

    def validate_schedule_date_time(self, value):
        if self.initial_data.get('schedule_send') and not value:
            raise serializers.ValidationError(
                "Schedule date and time must be provided when schedule_send is True."
            )
        return value

    def validate(self, data):
        if data.get('schedule_send') and not data.get('schedule_date_time'):
            raise serializers.ValidationError({
                'schedule_date_time': 'Schedule date and time is required when schedule_send is True.'
            })
        return data


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
            'template',
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

class SentEmailListSerializer(serializers.ModelSerializer):
    due_date = serializers.SerializerMethodField()

    class Meta:
        model = EmailManager
        fields = [
            'id',
            'to',
            'subject',
            'policy_number',
            'priority',
            'email_status',
            'sent_at',
            'due_date',
        ]

    def get_due_date(self, obj):
        try:
            payment = PaymentSchedule.objects.filter(
                renewal_case_id=obj.policy_number
            ).first()
            return payment.due_date if payment else None
        except Exception:
            return None
        
class EmailManagerInboxSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    html_message = serializers.SerializerMethodField()

    class Meta:
        model = EmailManagerInbox
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_message(self, obj):
        if not obj.message:
            return None
        import html
        text = html.unescape(obj.message)
        text = text.replace("\r", "").replace("\n", "<br>").strip()
        return text

    def get_html_message(self, obj):
        return obj.html_message

        
class EmailReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailReply
        fields = ['message', 'html_message']
        extra_kwargs = {
            'message': {'required': True}
        }
