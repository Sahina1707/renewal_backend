from rest_framework import serializers
from apps.renewals.models import RenewalCase
from apps.renewals.models import Competitor

class NotInterestedCaseSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source='case_number', read_only=True)
    
    customer = serializers.SerializerMethodField()
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    product = serializers.SerializerMethodField()
    
    reason = serializers.CharField(source='get_not_interested_reason_display', read_only=True)
    
    current_provider = serializers.CharField(source='competitor.name', allow_null=True, read_only=True)
    
    marked_date = serializers.DateField(source='not_interested_date', read_only=True)
    agent = serializers.SerializerMethodField()
    remarks = serializers.CharField(read_only=True)

    class Meta:
        model = RenewalCase
        fields = [
            'case_id', 
            'customer', 
            'policy_number', 
            'product', 
            'reason', 
            'current_provider', 
            'marked_date', 
            'agent', 
            'remarks'
        ]

    def get_customer(self, obj):
        return {
            "name": obj.customer.full_name,
            "email": obj.customer.email,
            "phone": obj.customer.phone
        }

    def get_product(self, obj):
        return {
            "name": getattr(obj.policy, 'product_name', 'General Insurance'),
            "amount": obj.renewal_amount
        }

    def get_agent(self, obj):
        return obj.assigned_to.get_full_name() if obj.assigned_to else "Unassigned"
    

class NotInterestedCaseUpdateSerializer(serializers.Serializer):
    not_interested_reason = serializers.ChoiceField(
        choices=RenewalCase.NOT_INTERESTED_REASON_CHOICES,
        required=True
    )
    not_interested_date = serializers.DateField(required=True)
    competitor_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_competitor_id(self, value):
        if value is not None:
            if not Competitor.objects.filter(id=value).exists():
                raise serializers.ValidationError("Invalid competitor_id")
        return value    