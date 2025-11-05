"""
Policy Timeline serializers for the Intelipro Insurance Policy Renewal System.
"""

from rest_framework import serializers
from .models import PolicyTimeline, PolicyTimelineEvent, CustomerTimelineSummary, PolicyTimelineFilter, CustomerPaymentSchedule, UpcomingPayment
from apps.customers.serializers import CustomerSerializer
from apps.policies.serializers import PolicySerializer
from apps.users.serializers import UserSerializer
# Import serializers that exist
try:
    from apps.customer_financial_profile.serializers import CustomerFinancialProfileSerializer
except ImportError:
    CustomerFinancialProfileSerializer = None

try:
    from apps.customer_family_medical_history.serializers import CustomerFamilyMedicalHistorySerializer
except ImportError:
    CustomerFamilyMedicalHistorySerializer = None

try:
    from apps.customer_assets.serializers import CustomerAssetsSerializer
except ImportError:
    CustomerAssetsSerializer = None

try:
    from apps.customer_vehicle.serializers import CustomerVehicleSerializer
except ImportError:
    CustomerVehicleSerializer = None

try:
    from apps.customer_communication_preferences.serializers import CustomerCommunicationPreferenceSerializer
except ImportError:
    CustomerCommunicationPreferenceSerializer = None

try:
    from apps.customer_policy_preferences.serializers import CustomerPolicyPreferenceSerializer
except ImportError:
    CustomerPolicyPreferenceSerializer = None

try:
    from apps.other_insurance_policies.serializers import OtherInsurancePolicySerializer
except ImportError:
    OtherInsurancePolicySerializer = None

try:
    from apps.ai_insights.serializers import AIInsightSerializer
except ImportError:
    AIInsightSerializer = None

try:
    from apps.ai_policy_recommendations.serializers import AIPolicyRecommendationSerializer
except ImportError:
    AIPolicyRecommendationSerializer = None

try:
    from apps.customer_payment_schedule.serializers import PaymentScheduleSerializer
except ImportError:
    PaymentScheduleSerializer = None


class PolicyTimelineSerializer(serializers.ModelSerializer):
    """Serializer for Policy Timeline model"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True)
    formatted_event_date = serializers.CharField(read_only=True)
    event_category_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = PolicyTimeline
        fields = [
            'id',
            'policy',
            'customer',
            'agent',
            'event_type',
            'event_title',
            'event_description',
            'event_date',
            'event_status',
            'premium_amount',
            'coverage_details',
            'discount_info',
            'outcome',
            'follow_up_required',
            'follow_up_date',
            'display_icon',
            'is_milestone',
            'sequence_order',
            'created_at',
            'updated_at',
            # Read-only fields
            'customer_name',
            'policy_number',
            'agent_name',
            'formatted_event_date',
            'event_category_display',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'customer_name',
            'policy_number',
            'agent_name',
            'formatted_event_date',
            'event_category_display',
        ]


class PolicyTimelineDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Policy Timeline with related objects"""
    
    customer = CustomerSerializer(read_only=True)
    policy = PolicySerializer(read_only=True)
    agent = UserSerializer(read_only=True)
    formatted_event_date = serializers.CharField(read_only=True)
    event_category_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = PolicyTimeline
        fields = [
            'id',
            'policy',
            'customer',
            'agent',
            'event_type',
            'event_title',
            'event_description',
            'event_date',
            'event_status',
            'premium_amount',
            'coverage_details',
            'discount_info',
            'outcome',
            'follow_up_required',
            'follow_up_date',
            'display_icon',
            'is_milestone',
            'sequence_order',
            'created_at',
            'updated_at',
            'formatted_event_date',
            'event_category_display',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'formatted_event_date',
            'event_category_display',
        ]


class PolicyTimelineCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Policy Timeline events"""
    
    class Meta:
        model = PolicyTimeline
        fields = [
            'policy',
            'customer',
            'agent',
            'event_type',
            'event_title',
            'event_description',
            'event_date',
            'event_status',
            'premium_amount',
            'coverage_details',
            'discount_info',
            'outcome',
            'follow_up_required',
            'follow_up_date',
            'display_icon',
            'is_milestone',
            'sequence_order',
        ]
    
    def validate(self, data):
        """Validate the timeline event data"""
        # Ensure customer matches the policy's customer
        if data.get('policy') and data.get('customer'):
            if data['policy'].customer != data['customer']:
                raise serializers.ValidationError(
                    "Customer must match the policy's customer"
                )
        
        # Ensure follow_up_date is provided if follow_up_required is True
        if data.get('follow_up_required') and not data.get('follow_up_date'):
            raise serializers.ValidationError(
                "Follow-up date is required when follow-up is marked as required"
            )
        
        return data


class PolicyTimelineEventSerializer(serializers.ModelSerializer):
    """Serializer for Policy Timeline Events"""
    
    class Meta:
        model = PolicyTimelineEvent
        fields = [
            'id',
            'timeline',
            'event_category',
            'event_title',
            'event_description',
            'event_date',
            'event_data',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomerTimelineSummarySerializer(serializers.ModelSerializer):
    """Serializer for Customer Timeline Summary"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    
    class Meta:
        model = CustomerTimelineSummary
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'total_events',
            'active_policies',
            'total_premium',
            'last_activity_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'customer_name', 'customer_code']


class PolicyTimelineFilterSerializer(serializers.ModelSerializer):
    """Serializer for Policy Timeline Filters"""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = PolicyTimelineFilter
        fields = [
            'id',
            'name',
            'filter_type',
            'filter_criteria',
            'is_default',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name']


class PolicyTimelineDetailViewSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for Policy Timeline detail view with all related data"""
    
    # Basic timeline data
    customer = CustomerSerializer(read_only=True)
    policy = PolicySerializer(read_only=True)
    agent = UserSerializer(read_only=True)
    formatted_event_date = serializers.CharField(read_only=True)
    event_category_display = serializers.CharField(read_only=True)
    
    # Related customer data
    financial_profile = serializers.SerializerMethodField()
    family_medical_history = serializers.SerializerMethodField()
    assets = serializers.SerializerMethodField()
    vehicles = serializers.SerializerMethodField()
    communication_preferences = serializers.SerializerMethodField()
    policy_preferences = serializers.SerializerMethodField()
    other_insurance_policies = serializers.SerializerMethodField()
    
    # AI insights and recommendations
    ai_insights = serializers.SerializerMethodField()
    ai_policy_recommendations = serializers.SerializerMethodField()
    
    # Payment information
    payment_schedules = serializers.SerializerMethodField()
    
    # Timeline events
    timeline_events = PolicyTimelineEventSerializer(many=True, read_only=True)
    
    class Meta:
        model = PolicyTimeline
        fields = [
            'id',
            'policy',
            'customer',
            'agent',
            'event_type',
            'event_title',
            'event_description',
            'event_date',
            'event_status',
            'premium_amount',
            'coverage_details',
            'discount_info',
            'outcome',
            'follow_up_required',
            'follow_up_date',
            'display_icon',
            'is_milestone',
            'sequence_order',
            'created_at',
            'updated_at',
            'formatted_event_date',
            'event_category_display',
            # Related data
            'financial_profile',
            'family_medical_history',
            'assets',
            'vehicles',
            'communication_preferences',
            'policy_preferences',
            'other_insurance_policies',
            'ai_insights',
            'ai_policy_recommendations',
            'payment_schedules',
            'timeline_events',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'formatted_event_date',
            'event_category_display',
        ]
    
    def get_financial_profile(self, obj):
        """Get customer financial profile"""
        try:
            if CustomerFinancialProfileSerializer:
                profile = obj.customer.financial_profile
                return CustomerFinancialProfileSerializer(profile).data
            return None
        except:
            return None
    
    def get_family_medical_history(self, obj):
        """Get customer family medical history"""
        try:
            if CustomerFamilyMedicalHistorySerializer:
                history = obj.customer.family_medical_history.filter(is_active=True)
                return CustomerFamilyMedicalHistorySerializer(history, many=True).data
            return []
        except:
            return []
    
    def get_assets(self, obj):
        """Get customer assets"""
        try:
            if CustomerAssetsSerializer:
                assets = obj.customer.assets.all()
                return CustomerAssetsSerializer(assets, many=True).data
            return []
        except:
            return []
    
    def get_vehicles(self, obj):
        """Get customer vehicles"""
        try:
            if CustomerVehicleSerializer:
                vehicles = []
                for asset in obj.customer.assets.all():
                    vehicles.extend(asset.vehicles.all())
                return CustomerVehicleSerializer(vehicles, many=True).data
            return []
        except:
            return []
    
    def get_communication_preferences(self, obj):
        """Get customer communication preferences"""
        try:
            if CustomerCommunicationPreferenceSerializer:
                preferences = obj.customer.detailed_communication_preferences.all()
                return CustomerCommunicationPreferenceSerializer(preferences, many=True).data
            return []
        except:
            return []
    
    def get_policy_preferences(self, obj):
        """Get customer policy preferences"""
        try:
            if CustomerPolicyPreferenceSerializer:
                preferences = obj.customer.policy_preferences.all()
                return CustomerPolicyPreferenceSerializer(preferences, many=True).data
            return []
        except:
            return []
    
    def get_other_insurance_policies(self, obj):
        """Get customer's other insurance policies"""
        try:
            if OtherInsurancePolicySerializer:
                policies = obj.customer.other_insurance_policies.filter(policy_status='active')
                return OtherInsurancePolicySerializer(policies, many=True).data
            return []
        except:
            return []
    
    def get_ai_insights(self, obj):
        """Get AI insights for customer"""
        try:
            if AIInsightSerializer:
                insights = obj.customer.ai_insights.filter(is_active=True)
                return AIInsightSerializer(insights, many=True).data
            return []
        except:
            return []
    
    def get_ai_policy_recommendations(self, obj):
        """Get AI policy recommendations for customer"""
        try:
            if AIPolicyRecommendationSerializer:
                recommendations = obj.customer.ai_policy_recommendations.filter(is_active=True)
                return AIPolicyRecommendationSerializer(recommendations, many=True).data
            return []
        except:
            return []
    
    def get_payment_schedules(self, obj):
        """Get payment schedules for customer"""
        try:
            # This would need to be connected through renewal cases
            # For now, return empty list
            return []
        except:
            return []


class PolicyTimelineDashboardSerializer(serializers.ModelSerializer):
    """Serializer for Policy Timeline Dashboard view"""
    
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_code = serializers.CharField(source='customer.customer_code', read_only=True)
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True)
    
    # Summary statistics
    total_events = serializers.SerializerMethodField()
    active_policies = serializers.SerializerMethodField()
    total_premium = serializers.SerializerMethodField()
    
    class Meta:
        model = PolicyTimeline
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'policy',
            'policy_number',
            'agent',
            'agent_name',
            'event_type',
            'event_title',
            'event_date',
            'event_status',
            'premium_amount',
            'is_milestone',
            'total_events',
            'active_policies',
            'total_premium',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'customer_code',
            'policy_number',
            'agent_name',
            'total_events',
            'active_policies',
            'total_premium',
        ]
    
    def get_total_events(self, obj):
        """Get total events for customer"""
        try:
            return PolicyTimeline.objects.filter(customer=obj.customer, is_deleted=False).count()
        except:
            return 0
    
    def get_active_policies(self, obj):
        """Get active policies count for customer"""
        try:
            return obj.customer.policies.filter(status='active').count()
        except:
            return 0
    
    def get_total_premium(self, obj):
        """Get total premium for customer"""
        try:
            total = 0
            for policy in obj.customer.policies.filter(status='active'):
                total += float(policy.premium_amount or 0)
            return total
        except:
            return 0

class UpcomingPaymentSerializer(serializers.ModelSerializer):
    """Serializer for UpcomingPayment model"""
    
    policy_type = serializers.CharField(source='policy.policy_type.name', read_only=True)
    policy_name = serializers.CharField(source='policy.policy_type.friendly_name', read_only=True) # Assuming a friendly name field exists
    
    class Meta:
        model = UpcomingPayment
        fields = [
            'id',
            'policy',
            'customer',
            'due_date',
            'amount_due',
            'days_to_due',
            'policy_type',
            'policy_name',
        ]
        read_only_fields = ['id', 'policy_type', 'policy_name']


class CustomerPaymentScheduleSerializer(serializers.ModelSerializer):
    """Serializer for CustomerPaymentSchedule model (The Main Payment Section)"""
    
    # We will fetch upcoming payments separately in the view for efficiency
    
    class Meta:
        model = CustomerPaymentSchedule
        fields = [
            'id',
            'customer',
            'total_payments_last_12_months',
            'on_time_payments_last_12_months',
            'total_paid_last_12_months',
            'average_payment_timing_days',
            'preferred_payment_method',
            'late_payment_instances',
        ]
        read_only_fields = ['id']

