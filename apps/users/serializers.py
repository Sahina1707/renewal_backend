# serializers.py
from rest_framework import serializers
from .models import User, Role


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'display_name', 'description', 'permissions']


class UserListSerializer(serializers.ModelSerializer):
    """Simplified serializer for user lists"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    assigned_customers_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role_name', 'department', 'job_title', 'status',
            'assigned_customers_count', 'phone', 'created_at'
        ]


class UserSerializer(serializers.ModelSerializer):
    """Full serializer for User model"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_details = RoleSerializer(source='role', read_only=True)
    assigned_customers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'department', 'job_title', 'employee_id',
            'role', 'role_name', 'role_details', 'avatar', 'bio',
            'timezone', 'language', 'status', 'email_notifications',
            'sms_notifications', 'theme_preference', 'last_login',
            'date_joined', 'created_at', 'updated_at',
            'assigned_customers_count'
        ]
        read_only_fields = [
            'id', 'last_login', 'date_joined', 'created_at', 'updated_at'
        ]
    
    def get_assigned_customers_count(self, obj):
        """Get count of assigned customers"""
        return obj.assigned_customers.count()


class AgentSelectionSerializer(serializers.ModelSerializer):
    """Simplified serializer for agent selection dropdowns"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    workload = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'role_name', 
            'department', 'status', 'workload'
        ]
    
    def get_workload(self, obj):
        """Get current workload count"""
        return obj.assigned_customers.filter(status='active').count()
