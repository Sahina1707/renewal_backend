from rest_framework import serializers
from .models import DistributionChannel
from apps.channels.models import Channel
from django.db.models import Sum
from apps.renewals.models import RenewalCase
class DistributionChannelSerializer(serializers.ModelSerializer):
    """Full serializer for DistributionChannel model with all fields"""
    current_policies = serializers.IntegerField(read_only=True)
    renewal_rate = serializers.FloatField(read_only=True)
    revenue = serializers.CharField(read_only=True)

    channel_id = serializers.PrimaryKeyRelatedField(
        queryset=Channel.objects.filter(is_deleted=False),
        source='channel',
        required=False,
        allow_null=True,
        help_text="ID of the related channel from channels table"
    )
    channel_name = serializers.CharField(
        source='channel.name',
        read_only=True
    )
    is_active = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = DistributionChannel
        fields = [
            'id',
            'name',
            'channel_type',
            'description',
            'channel_id',
            'channel_name',
            'contact_person',
            'contact_email',
            'contact_phone',
            'region',
            'commission_rate',
            'target_revenue',
            'status',
            'partner_since',
            'current_policies',
            'renewal_rate',
            'revenue',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by', 'is_active']
    
    def validate_name(self, value):
        """Validate channel name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Distribution channel name cannot be empty.")
        return value.strip()
    
    def validate_commission_rate(self, value):
        """Validate commission rate is between 0 and 100"""
        if value is not None:
            if value < 0 or value > 100:
                raise serializers.ValidationError("Commission rate must be between 0 and 100.")
        return value
    
    def validate_target_revenue(self, value):
        """Validate target revenue is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Target revenue cannot be negative.")
        return value
    
    def validate_channel_type(self, value):
        """Validate channel type is valid"""
        valid_types = [choice[0] for choice in DistributionChannel.CHANNEL_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid channel type. Valid options are: {', '.join(valid_types)}"
            )
        return value
    
    def validate_status(self, value):
        """Validate status is valid"""
        valid_statuses = [choice[0] for choice in DistributionChannel.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Valid options are: {', '.join(valid_statuses)}"
            )
        return value
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        from apps.renewals.models import RenewalCase

        renewal_cases = RenewalCase.objects.filter(channel=instance.channel)

        total_cases = renewal_cases.count()
        renewed_cases = renewal_cases.filter(status='renewed').count()

        data['current_policies'] = total_cases

        if total_cases > 0:
            data['renewal_rate'] = round((renewed_cases / total_cases) * 100, 1)
        else:
            data['renewal_rate'] = 0.0

        total_revenue = renewal_cases.filter(status='renewed') \
            .aggregate(total=Sum('renewal_amount')).get('total') or 0

        data['revenue'] = f"₹{float(total_revenue):.1f}L"

        return data


class DistributionChannelListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing distribution channels"""
    
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    current_policies = serializers.IntegerField(read_only=True)
    renewal_rate = serializers.FloatField(read_only=True)
    revenue = serializers.CharField(read_only=True)
    efficiency = serializers.FloatField(read_only=True)
    rating = serializers.FloatField(read_only=True)  
    
    class Meta:
        model = DistributionChannel
        fields = [
            'id',
            'name',
            'channel_type',
            'channel_name',
            'contact_person',
            'region',
            'commission_rate',
            'target_revenue',
            'status',
            'is_active',
            'partner_since',
            'current_policies',
            'renewal_rate',
            'revenue',
            'efficiency',
            'rating',
            'created_at',
        ]

    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        qs = RenewalCase.objects.filter(channel=instance.channel)

        total = qs.count()
        renewed = qs.filter(status='renewed').count()

        data['current_policies'] = total

        data['renewal_rate'] = round((renewed / total) * 100, 1) if total > 0 else 0.0

        total_revenue = qs.filter(status='renewed').aggregate(total=Sum('renewal_amount'))['total'] or 0
        data['revenue'] = f"₹{float(total_revenue)/100000:.1f}L"

        data['efficiency'] = round((renewed / total) * 100, 1) if total > 0 else 0.0

        data['rating'] = round((data['efficiency'] / 20), 1) 

        return data    


class DistributionChannelCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating distribution channels"""
    
    channel_id = serializers.PrimaryKeyRelatedField(
        queryset=Channel.objects.filter(is_deleted=False),
        source='channel',
        required=False,
        allow_null=True,
        help_text="ID of the related channel from channels table"
    )
    
    class Meta:
        model = DistributionChannel
        fields = [
            'name',
            'channel_type',
            'description',
            'channel_id',
            'contact_person',
            'contact_email',
            'contact_phone',
            'region',
            'commission_rate',
            'target_revenue',
            'status',
            'partner_since',
        ]
    
    def validate_name(self, value):
        """Validate channel name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Distribution channel name cannot be empty.")
        return value.strip()
    
    def validate_commission_rate(self, value):
        """Validate commission rate is between 0 and 100"""
        if value is not None:
            if value < 0 or value > 100:
                raise serializers.ValidationError("Commission rate must be between 0 and 100.")
        return value
    
    def validate_target_revenue(self, value):
        """Validate target revenue is not negative"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Target revenue cannot be negative.")
        return value
