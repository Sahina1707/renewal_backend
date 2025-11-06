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


class CaseCommentSerializer(serializers.ModelSerializer):
    """Serializer for case comments using CaseLog model"""
    
    comment_type = serializers.SerializerMethodField()
    is_internal = serializers.SerializerMethodField()
    is_important = serializers.SerializerMethodField()
    case = serializers.PrimaryKeyRelatedField(source='renewal_case', read_only=True)
    
    class Meta:
        model = CaseLog
        fields = [
            'id',
            'case',
            'comment',
            'comment_type',
            'is_internal',
            'is_important',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_comment_type(self, obj):
        
        return 'general'
    
    def get_is_internal(self, obj):
        return False
    
    def get_is_important(self, obj):
        return False


class CaseCommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating case comments using CaseLog model"""
    
    comment = serializers.CharField(required=True)
    comment_type = serializers.CharField(required=False, allow_blank=True)
    is_internal = serializers.BooleanField(required=False, default=False)
    is_important = serializers.BooleanField(required=False, default=False)
    
    class Meta:
        model = CaseLog
        fields = [
            'comment',
            'comment_type',
            'is_internal',
            'is_important',
        ]
    
    def create(self, validated_data):
        """Create a new comment using CaseLog"""
        validated_data.pop('comment_type', None)
        validated_data.pop('is_internal', None)
        validated_data.pop('is_important', None)
        
        validated_data['created_by'] = self.context['request'].user
        
        comment = super().create(validated_data)
        
        from apps.case_history.models import CaseHistory
        CaseHistory.objects.create(
            case=comment.renewal_case,
            action='comment_added',
            description=f"Comment added: {comment.comment[:100]}{'...' if len(comment.comment) > 100 else ''}",
            created_by=self.context['request'].user
        )
        
        return comment