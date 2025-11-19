from rest_framework import serializers
from django.db.models import Sum
from .models import Channel
from apps.target_audience.models import TargetAudience


class ChannelSerializer(serializers.ModelSerializer):
    """Serializer for Channel model"""

    manager_name = serializers.CharField(source='get_manager_name', read_only=True)
    target_audience_name = serializers.CharField(source='get_target_audience_name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    target_audience_id = serializers.PrimaryKeyRelatedField(
        queryset=TargetAudience.objects.all(),  # type: ignore[attr-defined]
        source='target_audience',
        required=False,
        allow_null=True
    )

    class Meta:
        model = Channel
        fields = [
            'id',
            'name',
            'channel_type',
            'description',
            'target_audience_id',
            'target_audience_name',
            'manager_name',
            'cost_per_lead',
            'budget',
            'status',
            'priority',
            'working_hours',
            'max_capacity',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_cost_per_lead(self, value):
        """Validate cost per lead is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Cost per lead cannot be negative.")
        return value
    
    def validate_budget(self, value):
        """Validate budget is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Budget cannot be negative.")
        return value
    
    def validate_max_capacity(self, value):
        """Validate max capacity is positive"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Max capacity must be a positive number.")
        return value


class ChannelListSerializer(serializers.ModelSerializer):

    manager_name = serializers.CharField(source='get_manager_name', read_only=True)
    target_audience_name = serializers.CharField(source='get_target_audience_name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Channel
        fields = [
            'id',
            'name',
            'channel_type',
            'description',
            'status',
            'priority',
            'manager_name',
            'target_audience_name',
            'cost_per_lead',
            'budget',
            'is_active',
            'created_at'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        total_cases = instance.renewal_cases.count()
        renewed_cases = instance.renewal_cases.filter(status='renewed').count()

        total_revenue = instance.renewal_cases.filter(status='renewed') \
            .aggregate(total=Sum('renewal_amount')).get('total') or 0
        revenue_value = float(total_revenue)

        if total_cases > 0:
            conversion_rate = round((renewed_cases / total_cases) * 100, 1)
        else:
            conversion_rate = 0.0

        budget_value = float(instance.budget or 0)
        if budget_value > 0:
            efficiency_pct = round(min(100.0, (revenue_value / budget_value) * 100.0), 1)
        else:
            efficiency_pct = 100.0 if revenue_value > 0 else 0.0

        data['cases'] = total_cases
        data['renewed'] = renewed_cases
        data['conversion'] = conversion_rate
        data['efficiency'] = efficiency_pct
        data['revenue'] = f"{revenue_value:.2f}"

        return data



class ChannelCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating channels"""
    
    class Meta:
        model = Channel
        fields = [
            'name',
            'channel_type',
            'description',
            'target_audience',
            'manager_name',
            'cost_per_lead',
            'budget',
            'status',
            'priority',
            'working_hours',
            'max_capacity',
        ]
    
    def validate_cost_per_lead(self, value):
        """Validate cost per lead is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Cost per lead cannot be negative.")
        return value
    
    def validate_budget(self, value):
        """Validate budget is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Budget cannot be negative.")
        return value


class ChannelCreateAPISerializer(serializers.ModelSerializer):
    """Serializer specifically for the new channel creation API"""

    target_audience_id = serializers.PrimaryKeyRelatedField(
        queryset=TargetAudience.objects.all(),  # type: ignore[attr-defined]
        source='target_audience',
        required=False,
        allow_null=True,
        help_text="ID of the target audience from target_audience table"
    )

    target_audience_name_input = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        help_text="Target audience name - will create new if doesn't exist"
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        style={'base_template': 'textarea.html'},
        help_text="Channel description"
    )

    target_audience_name = serializers.CharField(source='get_target_audience_name', read_only=True)

    class Meta:
        model = Channel
        fields = [
            'id',
            'name',
            'channel_type',
            'description',
            'target_audience_id',
            'target_audience_name_input',
            'target_audience_name',
            'manager_name',
            'cost_per_lead',
            'budget',
            'status',
            'priority',
            'working_hours',
            'max_capacity',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        """Validate channel name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Channel name cannot be empty.")
        return value.strip()

    def validate_manager_name(self, value):
        """Validate manager name"""
        if value and not value.strip():
            raise serializers.ValidationError("Manager name cannot be empty.")
        return value.strip() if value else value

    def validate_description(self, value):
        """Validate description field"""
        if value:
            return value.strip()
        return value

    def validate_channel_type(self, value):
        """Validate channel type is valid"""
        valid_types = [choice[0] for choice in Channel.CHANNEL_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid channel type. Valid options are: {', '.join(valid_types)}")
        return value

    def validate_status(self, value):
        """Validate status is one of allowed choices"""
        valid_status = [choice[0] for choice in Channel.STATUS_CHOICES]
        if value not in valid_status:
            raise serializers.ValidationError(f"Invalid status. Valid options are: {', '.join(valid_status)}")
        return value

    def validate_priority(self, value):
        """Validate priority is one of allowed choices"""
        valid_priority = [choice[0] for choice in Channel.PRIORITY_CHOICES]
        if value not in valid_priority:
            raise serializers.ValidationError(f"Invalid priority. Valid options are: {', '.join(valid_priority)}")
        return value

    def validate(self, attrs):
        """Custom validation to handle target_audience logic"""
        target_audience_id = attrs.get('target_audience')
        target_audience_name_input = attrs.get('target_audience_name_input')

        if target_audience_id and target_audience_name_input:
            raise serializers.ValidationError({
                'target_audience': 'Provide either target_audience_id OR target_audience_name_input, not both.'
            })

        return attrs

    def to_internal_value(self, data):
        """Handle legacy field names for backward compatibility"""
        if 'target_audience' in data and isinstance(data['target_audience'], str):
            data = data.copy()  
            data['target_audience_name_input'] = data.pop('target_audience')

        if 'manager' in data and 'manager_name' not in data:
            data = data.copy()
            data['manager_name'] = data.pop('manager')

        return super().to_internal_value(data)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        total_cases = instance.renewal_cases.count()

        renewed_cases = instance.renewal_cases.filter(status='renewed').count()

        total_revenue = instance.renewal_cases.filter(status='renewed') \
            .aggregate(total=Sum('renewal_amount')).get('total') or 0

        revenue_value = float(total_revenue)

        if total_cases > 0:
            conversion_rate = round((renewed_cases / total_cases) * 100, 1)
        else:
            conversion_rate = 0.0

        budget_value = float(instance.budget or 0)

        if budget_value > 0:
            efficiency_pct = round(min(100.0, (revenue_value / budget_value) * 100.0), 1)
        else:
            efficiency_pct = 100.0 if revenue_value > 0 else 0.0

        data['cases'] = total_cases
        data['renewed'] = renewed_cases
        data['conversion'] = conversion_rate
        data['revenue'] = f"{revenue_value:.2f}"
        data['efficiency'] = efficiency_pct

        return data


    def validate_cost_per_lead(self, value):
        """Validate cost per lead is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Cost per lead cannot be negative.")
        return value

    def validate_budget(self, value):
        """Validate budget is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Budget cannot be negative.")
        return value

    def create(self, validated_data):
        """Custom create method to handle target_audience creation"""
        target_audience_name_input = validated_data.pop('target_audience_name_input', None)

        if target_audience_name_input:
            target_audience_name_input = target_audience_name_input.strip()
            if target_audience_name_input:
                target_audience, created = TargetAudience.objects.get_or_create(  # type: ignore[attr-defined]
                    name__iexact=target_audience_name_input,
                    defaults={
                        'name': target_audience_name_input,
                        'key': target_audience_name_input.lower().replace(' ', '_'),
                        'description': f'Auto-created target audience: {target_audience_name_input}',
                        'created_by': self.context['request'].user if 'request' in self.context else None
                    }
                )
                validated_data['target_audience'] = target_audience

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Custom update method to handle target_audience creation"""
        target_audience_name_input = validated_data.pop('target_audience_name_input', None)

        if target_audience_name_input:
            target_audience_name_input = target_audience_name_input.strip()
            if target_audience_name_input:
                target_audience, created = TargetAudience.objects.get_or_create(  # type: ignore[attr-defined]
                    name__iexact=target_audience_name_input,
                    defaults={
                        'name': target_audience_name_input,
                        'key': target_audience_name_input.lower().replace(' ', '_'),
                        'description': f'Auto-created target audience: {target_audience_name_input}',
                        'created_by': self.context['request'].user if 'request' in self.context else None
                    }
                )
                validated_data['target_audience'] = target_audience

        return super().update(instance, validated_data)
