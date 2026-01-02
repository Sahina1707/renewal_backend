from rest_framework import serializers
from django.db.models import Q
from .models import DNCSettings, DNCRegistry, DNCOverrideLog
from apps.customers.models import Customer
from apps.renewals.models import RenewalCase


class DNCSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DNCSettings
        fields = '__all__'


class DNCRegistrySerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    client_id = serializers.IntegerField(source="client.id", read_only=True)  # ✅ NEW

    effective_date = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True
    )
    expiry_date = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True
    )

    class Meta:
        model = DNCRegistry
        fields = [
            'id',
            'customer',
            'client_id',          # ✅ NEW
            'client_name',
            'customer_name',
            'phone_number',
            'email_address',
            'dnc_type',
            'source',
            'status',
            'effective_date',
            'expiry_date',
            'allow_override_requests',
            'reason',
            'created_at'
        ]
        read_only_fields = ['customer', 'client_id']

    # ✅ VALIDATION (UNCHANGED)
    def validate(self, attrs):
        phone = attrs.get('phone_number')
        email = attrs.get('email_address')

        customer = Customer.objects.filter(
            Q(phone=phone) | Q(email=email)
        ).first()

        if not customer:
            raise serializers.ValidationError(
                "Customer does not exist. Only existing customers can be added to DNC."
            )

        attrs['_linked_customer'] = customer
        return attrs

    # ✅ CREATE (UNCHANGED)
    def create(self, validated_data):
        customer = validated_data.pop('_linked_customer', None)
        validated_data['customer'] = customer
        return super().create(validated_data)

    # ✅ FIXED + CORRECT CLIENT LOGIC
    def get_client_name(self, obj):
        try:
            # 1️⃣ If client already assigned (random or real)
            if obj.client:
                return obj.client.name

            # 2️⃣ Fallback via policy
            if obj.customer:
                policy = RenewalCase.objects.filter(customer=obj.customer).first()
                if policy and policy.distribution_channel:
                    return policy.distribution_channel.name

            return "Client Pending"
        except Exception:
            return "N/A"


class DNCOverrideLogSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source='dnc_entry.customer_name',
        read_only=True
    )
    dnc_status = serializers.CharField(
        source='dnc_entry.status',
        read_only=True
    )

    class Meta:
        model = DNCOverrideLog
        fields = [
            'id',
            'dnc_entry',
            'customer_name',
            'dnc_status',
            'override_type',
            'end_date',
            'reason',
            'authorized_by',
            'created_at'
        ]
