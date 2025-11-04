from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.renewals.models import RenewalCase
from .models import CaseLog

User = get_user_model()

class CaseLogSerializer(serializers.ModelSerializer):
    """Serializer for case logs - used in search functionality"""

    renewal_case_number = serializers.CharField(source='renewal_case.case_number', read_only=True)
    sub_status = serializers.CharField(source='get_sub_status_display', read_only=True)
    current_work_step = serializers.CharField(source='get_current_work_step_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    class Meta:
        model = CaseLog
        fields = [
            'id',
            'renewal_case',
            'renewal_case_number',
            'sub_status',
            'current_work_step',
            'next_follow_up_date',
            'next_action_plan',
            'comment',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None
