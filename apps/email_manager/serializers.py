from rest_framework import serializers
import re
import html
from .models import EmailManager
from apps.templates.models import Template
from apps.customer_payment_schedule.models import PaymentSchedule
from .models import EmailManagerInbox
from django.utils.html import strip_tags
from .models import EmailReply, StartedReplyMail, EmailManagerForwardMail


class EmailManagerSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = EmailManager
        fields = [
            'id',
            'from_email',
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
    def create(self, validated_data):
        instance = super().create(validated_data)

        if instance.schedule_send:
            instance.email_status = "scheduled"
            instance.save(update_fields=["email_status"])

        return instance



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
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)

        if instance.schedule_send:
            instance.email_status = "scheduled"
            instance.save(update_fields=["email_status"])

        return instance

class SentEmailListSerializer(serializers.ModelSerializer):
    due_date = serializers.SerializerMethodField()
    message_html = serializers.SerializerMethodField()
    message_preview = serializers.SerializerMethodField()

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
            'message',        
            'message_html',   
            'message_preview', 
        ]

    def get_due_date(self, obj):
        try:
            payment = PaymentSchedule.objects.filter(
                renewal_case_id=obj.policy_number
            ).first()
            return payment.due_date if payment else None
        except Exception:
            return None

    def get_message_html(self, obj):
        """Convert text message into simple HTML <br> format."""
        if not obj.message:
            return ""
        return obj.message.replace("\n", "<br/>")

    def get_message_preview(self, obj):
        raw = obj.message or ""
        raw = strip_tags(raw)
        return raw[:120] + "..." if len(raw) > 120 else raw

class EmailManagerInboxSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    html_message = serializers.SerializerMethodField()
    clean_text = serializers.SerializerMethodField()
    class Meta:
        model = EmailManagerInbox
        fields = [
            'id',
            'from_email',
            'to_email',
            'subject',
            'message',
            'html_message',
            'clean_text',     
            'received_at',
            'related_email',
            'is_read',
            'in_reply_to',
            'started',
            'created_at',
            'updated_at',
            'is_deleted',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_message(self, obj):
        if not obj.message:
            return None
        text = html.unescape(obj.message)
        text = text.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
        while "<br><br>" in text:
            text = text.replace("<br><br>", "<br>")

        return text.strip()


    def get_html_message(self, obj):
        return obj.html_message
    
    def get_clean_text(self, obj):
        content = obj.html_message or obj.message or ""
        content = content.replace("<br>", "\n").replace("</p>", "\n").replace("<p>", "")
        clean = strip_tags(content)
        clean = re.sub(r'\n+', '\n', clean).strip()
        return clean

        
class EmailReplySerializer(serializers.ModelSerializer):
    template_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    class Meta:
        model = EmailReply
        fields = ['message', 'html_message', 'template_id']
        extra_kwargs = {
            'message': {'required': False},
        }

    def validate(self, data):
        if not data.get('message') and not data.get('template_id'):
            raise serializers.ValidationError(
                "Either message or template_id must be provided."
            )
        return data
    
class EmailReplyStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailReply
        fields = ['started']

class StartedReplyMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartedReplyMail
        fields = "__all__"
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

class EmailForwardSerializer(serializers.Serializer):
    forward_to = serializers.EmailField(required=True)
    cc = serializers.CharField(required=False, allow_blank=True)
    bcc = serializers.CharField(required=False, allow_blank=True)
    additional_message = serializers.CharField(required=False, allow_blank=True)
    template_id = serializers.IntegerField(required=False, allow_null=True)

class EmailManagerForwardMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailManagerForwardMail
        fields = "__all__"
        read_only_fields = ["id", "sent_at", "created_at", "updated_at", "status"]
