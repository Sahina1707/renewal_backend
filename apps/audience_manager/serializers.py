from rest_framework import serializers
from .models import Audience, AudienceContact

class AudienceContactSerializer(serializers.ModelSerializer):
    """Serializer for AudienceContact (used for listing and manual entry)"""
    
    class Meta:
        model = AudienceContact
        fields = [
            'id', 'audience', 'name', 'email', 'phone', 'policy_number'
        ]
        read_only_fields = ['id']


class AudienceContactWriteSerializer(serializers.Serializer):
    """Serializer used for adding multiple contacts via bulk upload or manual batch."""
    
    name = serializers.CharField(max_length=200)
    # --- UPDATE: Make email optional at the field level ---
    email = serializers.EmailField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    policy_number = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)

    # --- UPDATE: Add a validation method ---
    def validate(self, data):
        """
        Check that at least an email or a phone number is provided.
        """
        email = data.get('email')
        phone = data.get('phone')

        # Handle empty strings
        if not email and not phone:
             raise serializers.ValidationError("At least one of 'email' or 'phone' is required.")
        
        # Standardize empty strings to None to work with database constraints
        if email == "":
            data['email'] = None
        if phone == "":
            data['phone'] = None
            
        return data


class AudienceSerializer(serializers.ModelSerializer):
    """Main serializer for Audience (used for listing cards and detail view)"""
    
    contacts = AudienceContactSerializer(many=True, read_only=True) 
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = Audience
        fields = [
            'id', 'name', 'description', 'segments', 'contact_count', 'last_updated', 'created_at',
            'created_by_name', 'contacts'
        ]
        read_only_fields = [
            'id', 'contact_count', 'last_updated', 'created_at'
        ]


class AudienceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating the Audience definition."""
    
    segments_csv = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = Audience
        fields = [
            'name', 'description', 'segments_csv'
        ]

    def validate_segments_csv(self, value):
        if value:
            return [s.strip() for s in value.split(',') if s.strip()]
        return []
    
    def create(self, validated_data):
        if 'segments_csv' in validated_data:
            validated_data['segments'] = validated_data.pop('segments_csv')
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        if 'segments_csv' in validated_data:
            validated_data['segments'] = validated_data.pop('segments_csv')
        return super().update(instance, validated_data)