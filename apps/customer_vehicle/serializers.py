from rest_framework import serializers
from .models import CustomerVehicle
from apps.customer_assets.models import CustomerAssets
class CustomerVehicleSerializer(serializers.ModelSerializer):
    """Serializer for CustomerVehicle model"""
    
    customer_name = serializers.CharField(source='customer_assets.customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer_assets.customer.customer_code', read_only=True)
    vehicle_summary = serializers.CharField(read_only=True)
    vehicle_score = serializers.IntegerField(read_only=True)
    depreciation_rate = serializers.FloatField(read_only=True)
    vehicle_age = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CustomerVehicle
        fields = [
            'id',
            'customer_assets',
            'customer_name',
            'customer_code',
            'vehicle_name',
            'model_year',
            'vehicle_type',
            'fuel_type',
            'condition',
            'value',
            'purchase_price',
            'registration_number',
            'engine_capacity',
            'mileage',
            'vehicle_summary',
            'vehicle_score',
            'depreciation_rate',
            'vehicle_age',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class CustomerVehicleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CustomerVehicle"""
    
    class Meta:
        model = CustomerVehicle
        fields = [
            'customer_assets',
            'vehicle_name',
            'model_year',
            'vehicle_type',
            'fuel_type',
            'condition',
            'value',
            'purchase_price',
            'registration_number',
            'engine_capacity',
            'mileage',
        ]


class CustomerVehicleUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CustomerVehicle"""
    
    class Meta:
        model = CustomerVehicle
        fields = [
            'vehicle_name',
            'model_year',
            'vehicle_type',
            'fuel_type',
            'condition',
            'value',
            'purchase_price',
            'registration_number',
            'engine_capacity',
            'mileage',
        ]


class CustomerVehicleListSerializer(serializers.ModelSerializer):
    """Serializer for listing CustomerVehicle with minimal data"""
    
    customer_name = serializers.CharField(source='customer_assets.customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer_assets.customer.customer_code', read_only=True)
    customer_email = serializers.CharField(source='customer_assets.customer.email', read_only=True)
    vehicle_summary = serializers.CharField(read_only=True)
    vehicle_score = serializers.IntegerField(read_only=True)
    vehicle_age = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CustomerVehicle
        fields = [
            'id',
            'customer_assets',
            'customer_name',
            'customer_code',
            'customer_email',
            'vehicle_name',
            'model_year',
            'vehicle_type',
            'fuel_type',
            'condition',
            'value',
            'registration_number',
            'vehicle_summary',
            'vehicle_score',
            'vehicle_age',
            'created_at',
        ]
