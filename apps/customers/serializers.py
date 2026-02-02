# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Customer
from apps.channels.serializers import ChannelSerializer

User = get_user_model()


class AgentSerializer(serializers.ModelSerializer):
    """Serializer for agent information"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'role_name', 'department', 'status']


class CustomerSerializer(serializers.ModelSerializer):
    """Enhanced Customer serializer with agent information"""
    assigned_agent_details = AgentSerializer(source='assigned_agent', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    channels = ChannelSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = '__all__'

    def to_representation(self, instance):
        """Customize the representation to include additional computed fields"""
        data = super().to_representation(instance)

        data['full_name'] = instance.full_name

        if instance.assigned_agent:
            data['agent_summary'] = {
                'id': instance.assigned_agent.id,
                'name': instance.assigned_agent.get_full_name(),
                'email': instance.assigned_agent.email,
                'role': instance.assigned_agent.role.name if instance.assigned_agent.role else None
            }
        else:
            data['agent_summary'] = None

        return data


class CustomerListSerializer(serializers.ModelSerializer):
    """Simplified serializer for customer lists"""
    assigned_agent_name = serializers.CharField(source='assigned_agent.get_full_name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'customer_code', 'full_name', 'email', 'phone',
            'status', 'priority', 'profile', 'total_policies',
            'city', 'state', 'assigned_agent', 'assigned_agent_name',
            'created_at', 'updated_at'
        ]

class AgentAssignmentSerializer(serializers.Serializer):
    """Serializer for agent assignment requests"""
    agent_id = serializers.IntegerField()

    def validate_agent_id(self, value):
        """Validate that the agent exists and is active"""
        try:
            agent = User.objects.get(id=value, status='active', is_active=True)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Agent not found or inactive")


class BulkAgentAssignmentSerializer(serializers.Serializer):
    """Serializer for bulk agent assignment requests"""
    assignments = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        ),
        min_length=1
    )

    def validate_assignments(self, value):
        """Validate assignment data structure"""
        for assignment in value:
            if 'customer_id' not in assignment or 'agent_id' not in assignment:
                raise serializers.ValidationError(
                    "Each assignment must contain 'customer_id' and 'agent_id'"
                )
        return value