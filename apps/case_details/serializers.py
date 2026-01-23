from rest_framework import serializers
from apps.customers.models import Customer
from apps.customers_files.models import CustomerFile
from apps.policies.models import Policy, PolicyType, PolicyAgent
from apps.customer_financial_profile.models import CustomerFinancialProfile
from apps.channels.models import Channel
from apps.policy_features.models import PolicyFeature
from apps.policy_coverages.models import PolicyCoverage
from apps.policy_additional_benefits.models import PolicyAdditionalBenefit
from apps.policy_exclusions.models import PolicyExclusion
from apps.customer_communication_preferences.models import CustomerCommunicationPreference
class CustomerDocumentSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    class Meta:
        model = CustomerFile
        exclude = ['customer']
    
    def get_customer_name(self, obj):
        """Get customer name instead of customer ID"""
        if obj.customer:
            name = f"{obj.customer.first_name} {obj.customer.last_name}".strip()
            return name if name else obj.customer.customer_code
        return None
class CustomerFinancialProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerFinancialProfile
        exclude = ['customer']
class PolicyCoverageSerializer(serializers.ModelSerializer):
    additional_benefits = serializers.SerializerMethodField()

    class Meta:
        model = PolicyCoverage
        fields = '__all__'

    def get_additional_benefits(self, obj):
        benefits = PolicyAdditionalBenefit.objects.filter(policy_coverages=obj)
        return PolicyAdditionalBenefitSerializer(benefits, many=True).data
class PolicyAdditionalBenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyAdditionalBenefit
        fields = '__all__'


class PolicyFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyFeature
        fields = '__all__'


class PolicyExclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyExclusion
        fields = '__all__'


class PolicyTypeSerializer(serializers.ModelSerializer):
    policy_features = serializers.SerializerMethodField()
    policy_coverages = PolicyCoverageSerializer(many=True, read_only=True)

    class Meta:
        model = PolicyType
        fields = '__all__'
    
    def get_policy_features(self, obj):
        """Get only mandatory active policy features for this specific policy"""
        policy = self.context.get('policy', None)
        
        features = PolicyFeature.objects.filter(
            policy_type=obj,
            is_active=True,
            is_deleted=False
        )
        
      
        if policy:
            features = features.filter(is_mandatory=True)
        
        features = features.order_by('display_order', 'feature_name')
        return PolicyFeatureSerializer(features, many=True).data


class ChannelSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='name', read_only=True)
    channel_type = serializers.CharField(read_only=True)
    manager_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Channel
        fields = ['channel_name', 'channel_type', 'manager_name']


class PolicyAgentSerializer(serializers.ModelSerializer):
    """Serializer for PolicyAgent details"""
    agent_code = serializers.CharField(read_only=True)
    agent_name = serializers.CharField(read_only=True)
    contact_number = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    
    class Meta:
        model = PolicyAgent
        fields = ['id', 'agent_code', 'agent_name', 'contact_number', 'email']


class PolicySerializer(serializers.ModelSerializer):
    policy_type = serializers.SerializerMethodField()
    exclusions = PolicyExclusionSerializer(many=True, read_only=True)
    agent_details = PolicyAgentSerializer(source='agent', read_only=True)

    class Meta:
        model = Policy
        exclude = ['customer', 'agent']
    
    def get_policy_type(self, obj):
        """Get policy type with policy context for filtering features"""
        serializer = PolicyTypeSerializer(obj.policy_type, context={'policy': obj})
        return serializer.data

class CustomerSerializer(serializers.ModelSerializer):
    documents = CustomerDocumentSerializer(many=True, read_only=True, source='customer_files')
    financial_profile = CustomerFinancialProfileSerializer(read_only=True)
    channel = ChannelSerializer(read_only=True, source='channel_id')
    policies = PolicySerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = '__all__'

class CustomerCommunicationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerCommunicationPreference
        fields = "__all__"
