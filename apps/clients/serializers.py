from rest_framework import serializers
from .models import Client

class ClientSerializer(serializers.ModelSerializer):

    insurance_type_label = serializers.CharField(
        source="get_insurance_type_display",
        read_only=True
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "code",
            "insurance_type",
            "insurance_type_label",
            "description",
            "contact_number",
            "email",
            "is_active",
            "created_at",
        ]
