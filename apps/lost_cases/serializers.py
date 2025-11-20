from rest_framework import serializers
from apps.renewals.models import RenewalCase

class LostCaseListSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source='case_number', read_only=True)
    customer = serializers.SerializerMethodField()
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    product = serializers.SerializerMethodField()    
    lost_reason = serializers.CharField(source='get_lost_reason_display', read_only=True)
    competitor = serializers.CharField(source='competitor.name', allow_null=True, read_only=True)    
    agent = serializers.SerializerMethodField()
    attempts = serializers.IntegerField(source='communication_attempts_count', read_only=True)

    class Meta:
        model = RenewalCase
        fields = [
            'case_id', 
            'customer', 
            'policy_number', 
            'product',   # Now contains name and amount
            'lost_reason', 
            'competitor', 
            'lost_date', 
            'agent', 
            'attempts'
        ]

    def get_customer(self, obj):
        return {
            "name": obj.customer.full_name,
            "email": obj.customer.email,
            "phone": obj.customer.phone
        }

    def get_product(self, obj):
        """
        Returns product details including the name and the renewal amount.
        """
        product_name = getattr(obj.policy, 'product_name', 'General Insurance') 
        
        return {
            "name": product_name,
            "amount": obj.renewal_amount
        }

    def get_agent(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return "Unassigned"