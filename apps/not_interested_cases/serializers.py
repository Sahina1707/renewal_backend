from rest_framework import serializers
from apps.renewals.models import RenewalCase

class NotInterestedCaseSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source='case_number', read_only=True)
    
    # 1. Customer Group
    customer = serializers.SerializerMethodField()
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    product = serializers.SerializerMethodField()
    
    # 3. The "Reason" Badge
    reason = serializers.CharField(source='get_not_interested_reason_display', read_only=True)
    
    # 4. "Current Provider" (Mapped from the competitor table)
    current_provider = serializers.CharField(source='competitor.name', allow_null=True, read_only=True)
    
    # 5. Other Fields
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