from rest_framework import serializers
from apps.renewals.models import RenewalCase
class ArchiveCaseActionSerializer(serializers.ModelSerializer):
    case_ids = serializers.ListField(child=serializers.CharField(), write_only=True)
    class Meta:
        model = RenewalCase
        fields = ['case_ids', 'archived_reason', 'archived_date', 'is_archived']
        extra_kwargs = {
            'archived_reason': {'required': False},
            'archived_date': {'required': False},
        }

class ArchivedCaseListSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source='case_number', read_only=True)

    customer = serializers.SerializerMethodField()

    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    product = serializers.SerializerMethodField()

    final_status = serializers.CharField(source='get_status_display', read_only=True)

    agent = serializers.SerializerMethodField()

    class Meta:
        model = RenewalCase
        fields = [
            'case_id', 
            'customer', 
            'policy_number', 
            'product', 
            'final_status',
            'archived_reason',
            'archived_date', 
            'agent', 
            'remarks',
        ]

    def get_customer(self, obj):
        return {"name": obj.customer.full_name, "email": obj.customer.email, "phone": obj.customer.phone}

    def get_product(self, obj):
        return {"name": getattr(obj.policy, 'product_name', 'Insurance'), "amount": obj.renewal_amount}

    def get_agent(self, obj):
        return obj.assigned_to.get_full_name() if obj.assigned_to else "Unassigned"
class ArchiveSingleCaseSerializer(serializers.Serializer):
    is_archived = serializers.BooleanField(required=True)
    archived_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )
    archived_date = serializers.DateField(required=False)

    def validate(self, attrs):
        is_archived = attrs.get("is_archived")

        if is_archived and not attrs.get("archived_reason"):
            pass

        return attrs