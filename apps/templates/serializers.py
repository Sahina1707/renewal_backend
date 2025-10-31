from rest_framework import serializers
from .models import Template


class TemplateSerializer(serializers.ModelSerializer):
    """Serializer for Template model"""
    
    class Meta:
        model = Template
        fields = [
            'id',
            'name', 
            'template_type',
            'channel',
            'category',
            'subject',
            'content',
            'variables',
            'dlt_template_id',
            'tags',
            'is_dlt_approved',
            'is_active',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class TemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Template instances"""
    
    class Meta:
        model = Template
        fields = [
            'name',
            'template_type',
            'channel',
            'category',
            'subject',
            'content',
            'variables',
            'dlt_template_id',
            'tags',
            'is_dlt_approved',
            'is_active'
        ]
    
    def validate_name(self, value):
        """Validate template name uniqueness"""
        if Template.objects.filter(name=value).exists():
            raise serializers.ValidationError("A template with this name already exists.")
        return value

    def validate_tags(self, value):
        """Ensure provided tags are within the allowed list."""
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise serializers.ValidationError("Tags must be provided as a list.")

        invalid = [tag for tag in value if tag not in Template.TAG_OPTIONS]
        if invalid:
            raise serializers.ValidationError(
                f"Invalid tag(s): {', '.join(invalid)}. Allowed tags are: {', '.join(Template.TAG_OPTIONS)}."
            )

        seen = set()
        deduped = []
        for tag in value:
            if tag not in seen:
                seen.add(tag)
                deduped.append(tag)
        return deduped


class TemplateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Template instances"""
    
    class Meta:
        model = Template
        fields = [
            'name',
            'template_type',
            'channel',
            'category',
            'subject',
            'content',
            'variables',
            'dlt_template_id',
            'tags',
            'is_dlt_approved',
            'is_active'
        ]
    
    def validate_name(self, value):
        """Validate template name uniqueness (excluding current instance)"""
        if self.instance and Template.objects.filter(name=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("A template with this name already exists.")
        return value

    def validate_tags(self, value):
        """Ensure provided tags are within the allowed list."""
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise serializers.ValidationError("Tags must be provided as a list.")

        invalid = [tag for tag in value if tag not in Template.TAG_OPTIONS]
        if invalid:
            raise serializers.ValidationError(
                f"Invalid tag(s): {', '.join(invalid)}. Allowed tags are: {', '.join(Template.TAG_OPTIONS)}."
            )

        # Return unique tags preserving order
        seen = set()
        deduped = []
        for tag in value:
            if tag not in seen:
                seen.add(tag)
                deduped.append(tag)
        return deduped
