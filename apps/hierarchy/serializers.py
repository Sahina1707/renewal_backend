from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Region, State, Branch, Department, Team

# Import Role model to check permissions
try:
    from apps.users.models import Role
except ImportError:
    from users.models import Role

User = get_user_model()

# --- BASE SERIALIZER (Shared Logic) ---
class NodeSerializer(serializers.ModelSerializer):
    # INPUT: Accepts Database ID (e.g., "9")
    manager_id = serializers.CharField(write_only=True)
    
    # OUTPUT: Shows Manager Name (e.g., "Sahina")
    manager_name = serializers.CharField(source='manager.first_name', read_only=True)

    def validate_manager_id(self, value):
        """
        LOGIC:
        1. Find User by Database ID (pk).
        2. Check if they have a Role.
        3. Check if Role is 'Manager' or 'Admin' (Flexible check).
        """
        # STEP 1: Find User by ID (Primary Key)
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(f"User with Database ID '{value}' not found.")

        # STEP 2: Check Role Existence
        if not user.role:
             raise serializers.ValidationError(f"User '{user.first_name}' has no role assigned.")
        
        # STEP 3: Verify Role Name (Flexible)
        # Allows 'manager', 'campaign_manager', 'admin', 'super_admin', etc.
        role_name = user.role.name.lower()
        if 'manager' not in role_name and 'admin' not in role_name:
            raise serializers.ValidationError(
                f"User '{user.first_name}' is a '{user.role.name}'. This role is not allowed."
            )

        return user

    def create(self, validated_data):
        # LOGIC FOR CREATING (POST)
        # Swap the raw ID for the actual User object
        if 'manager_id' in validated_data:
            validated_data['manager'] = validated_data.pop('manager_id')
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # LOGIC FOR EDITING (PUT/PATCH) - THIS FIXES YOUR ERROR
        # Swap the raw ID for the actual User object
        if 'manager_id' in validated_data:
            validated_data['manager'] = validated_data.pop('manager_id')
        return super().update(instance, validated_data)

# --- INDIVIDUAL SERIALIZERS (With Parent Logic) ---

class RegionSerializer(NodeSerializer):
    # Region is Root -> No parent_id
    level = serializers.SerializerMethodField()
    def get_level(self, obj): return "Region"
    class Meta:
        model = Region
        fields = ['id', 'unit_name', 'description', 'manager_id', 'manager_name', 'budget', 'target_cases', 'status', 'level']

class StateSerializer(NodeSerializer):
    # Map parent_id -> region
    parent_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='region', write_only=True)
    
    level = serializers.SerializerMethodField()
    def get_level(self, obj): return "State"
    class Meta:
        model = State
        fields = ['id', 'unit_name', 'parent_id', 'description', 'manager_id', 'manager_name', 'budget', 'target_cases', 'status', 'level']

class BranchSerializer(NodeSerializer):
    # Map parent_id -> state
    parent_id = serializers.PrimaryKeyRelatedField(queryset=State.objects.all(), source='state', write_only=True)
    
    level = serializers.SerializerMethodField()
    def get_level(self, obj): return "Branch"
    class Meta:
        model = Branch
        fields = ['id', 'unit_name', 'parent_id', 'description', 'manager_id', 'manager_name', 'budget', 'target_cases', 'status', 'level']

class DepartmentSerializer(NodeSerializer):
    # Map parent_id -> branch
    parent_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), source='branch', write_only=True)
    
    level = serializers.SerializerMethodField()
    def get_level(self, obj): return "Department"
    class Meta:
        model = Department
        fields = ['id', 'unit_name', 'parent_id', 'description', 'manager_id', 'manager_name', 'budget', 'target_cases', 'status', 'level']

class TeamSerializer(NodeSerializer):
    # Map parent_id -> department
    parent_id = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), source='department', write_only=True)
    
    level = serializers.SerializerMethodField()
    def get_level(self, obj): return "Team"
    class Meta:
        model = Team
        fields = ['id', 'unit_name', 'parent_id', 'description', 'manager_id', 'manager_name', 'budget', 'target_cases', 'status', 'level']