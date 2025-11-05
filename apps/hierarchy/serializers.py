"""
Serializers for Hierarchy Management API endpoints.
"""

from rest_framework import serializers
from django.db.models import Sum
from .models import HierarchyManagement
from apps.renewals.models import RenewalCase
from apps.users.models import User
import re

class HierarchyManagementSerializer(serializers.ModelSerializer):
    parent_unit_display = serializers.SerializerMethodField()
    cases = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    efficiency = serializers.SerializerMethodField()
    
    class Meta:
        model = HierarchyManagement
        fields = [
            'id',
            'unit_name',
            'unit_type',
            'description',
            'parent_unit',
            'parent_unit_display',
            'manager_id',
            'budget',
            'target_cases',
            'status',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'is_deleted',
            'cases',
            'revenue',
            'efficiency'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'parent_unit_display', 'cases', 'revenue', 'efficiency']
    
    def get_parent_unit_display(self, obj):
        return dict(obj.PARENT_UNIT_CHOICES).get(obj.parent_unit, obj.parent_unit)
    
    def get_cases(self, obj):
        """Get total cases assigned to this hierarchy unit's manager"""
        try:
            manager_number = obj.manager_id.split('-')[1] if '-' in obj.manager_id else obj.manager_id
            user = User.objects.filter(employee_id__icontains=manager_number).first()
            if user:
                return RenewalCase.objects.filter(assigned_to=user).count()
        except (IndexError, AttributeError):
            pass
        return 0
    
    def get_revenue(self, obj):
        """Get total revenue from renewed cases assigned to this hierarchy unit's manager"""
        try:
            manager_number = obj.manager_id.split('-')[1] if '-' in obj.manager_id else obj.manager_id
            user = User.objects.filter(employee_id__icontains=manager_number).first()
            if user:
                result = RenewalCase.objects.filter(
                    assigned_to=user, 
                    status='renewed'
                ).aggregate(total=Sum('renewal_amount'))
                return float(result['total'] or 0)
        except (IndexError, AttributeError):
            pass
        return 0.0
    
    def get_efficiency(self, obj):
        """Calculate efficiency as percentage of renewed cases"""
        try:
            manager_number = obj.manager_id.split('-')[1] if '-' in obj.manager_id else obj.manager_id
            user = User.objects.filter(employee_id__icontains=manager_number).first()
            if user:
                total_cases = RenewalCase.objects.filter(assigned_to=user).count()
                renewed_cases = RenewalCase.objects.filter(assigned_to=user, status='renewed').count()
                if total_cases > 0:
                    return round((renewed_cases / total_cases) * 100, 1)
        except (IndexError, AttributeError):
            pass
        return 0.0


class HierarchyManagementCreateSerializer(serializers.ModelSerializer):
    parent_unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = HierarchyManagement
        fields = [
            'unit_name',
            'unit_type',
            'description',
            'parent_unit',
            'manager_id',
            'budget',
            'target_cases',
            'status'
        ]
    
    def validate_parent_unit(self, value):
        if value in ['none', '', None]:
            return 'none'
        
        value = str(value).strip()
        
        valid_choices = [choice[0] for choice in HierarchyManagement.PARENT_UNIT_CHOICES]
        choice_dict = dict(HierarchyManagement.PARENT_UNIT_CHOICES)
        
        if value in valid_choices:
            return value
        
        if value in choice_dict.values():
            for choice_value, choice_display in HierarchyManagement.PARENT_UNIT_CHOICES:
                if choice_display == value:
                    return choice_value
        
        if '(' in value and ')' in value:
            unit_name_part = value.split('(')[0].strip()
            unit_slug = unit_name_part.lower().replace(' ', '_').replace('-', '_')
            if unit_slug in valid_choices:
                return unit_slug
        
        value_slug = value.lower().strip().replace(' ', '_').replace('-', '_')
        if value_slug in valid_choices:
            return value_slug
        
        value_lower = value.lower().strip()
        for choice_value, choice_display in HierarchyManagement.PARENT_UNIT_CHOICES:
            if value_lower == choice_display.lower():
                return choice_value
            display_unit_name = choice_display.split('(')[0].strip().lower()
            if value_lower == display_unit_name:
                return choice_value
            display_unit_slug = display_unit_name.replace(' ', '_').replace('-', '_')
            if value_lower == display_unit_slug or value_lower.replace(' ', '_') == display_unit_slug:
                return choice_value
        
        matching_unit = HierarchyManagement.objects.filter(
            is_deleted=False,
            unit_name__iexact=value
        ).first()
        
        if matching_unit:
            unit_slug = matching_unit.unit_name.lower().replace(' ', '_').replace('-', '_')
            if unit_slug in valid_choices:
                return unit_slug
        
        return 'none'
    
    def validate_manager_id(self, value):
        if not re.match(r'^mgr-\d{3}$', value):
            raise serializers.ValidationError("Manager ID must be in format mgr-XXX (e.g., mgr-002)")
        return value


class HierarchyManagementListSerializer(serializers.ModelSerializer):

    parent_unit_display = serializers.SerializerMethodField()
    unit_type_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    cases = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    efficiency = serializers.SerializerMethodField()
    
    class Meta:
        model = HierarchyManagement
        fields = [
            'id',
            'unit_name',
            'unit_type',
            'unit_type_display',
            'parent_unit',
            'parent_unit_display',
            'manager_id',
            'budget',
            'target_cases',
            'status',
            'status_display',
            'created_at',
            'cases',
            'revenue',
            'efficiency'
        ]
    
    def get_parent_unit_display(self, obj):
        return dict(obj.PARENT_UNIT_CHOICES).get(obj.parent_unit, obj.parent_unit)
    
    def get_unit_type_display(self, obj):
        return obj.get_unit_type_display()
    
    def get_status_display(self, obj):
        return obj.get_status_display()
    
    def get_cases(self, obj):
        """Get total cases assigned to this hierarchy unit's manager"""
        try:
            manager_number = obj.manager_id.split('-')[1] if '-' in obj.manager_id else obj.manager_id
            user = User.objects.filter(employee_id__icontains=manager_number).first()
            if user:
                return RenewalCase.objects.filter(assigned_to=user).count()
        except (IndexError, AttributeError):
            pass
        return 0
    
    def get_revenue(self, obj):
        """Get total revenue from renewed cases assigned to this hierarchy unit's manager"""
        try:
            manager_number = obj.manager_id.split('-')[1] if '-' in obj.manager_id else obj.manager_id
            user = User.objects.filter(employee_id__icontains=manager_number).first()
            if user:
                result = RenewalCase.objects.filter(
                    assigned_to=user, 
                    status='renewed'
                ).aggregate(total=Sum('renewal_amount'))
                return float(result['total'] or 0)
        except (IndexError, AttributeError):
            pass
        return 0.0
    
    def get_efficiency(self, obj):
        """Calculate efficiency as percentage of renewed cases"""
        try:
            manager_number = obj.manager_id.split('-')[1] if '-' in obj.manager_id else obj.manager_id
            user = User.objects.filter(employee_id__icontains=manager_number).first()
            if user:
                total_cases = RenewalCase.objects.filter(assigned_to=user).count()
                renewed_cases = RenewalCase.objects.filter(assigned_to=user, status='renewed').count()
                if total_cases > 0:
                    return round((renewed_cases / total_cases) * 100, 1)
        except (IndexError, AttributeError):
            pass
        return 0.0
