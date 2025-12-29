from rest_framework import serializers
from .models import BillingPeriod, UsageCharge, PlatformCharge, Invoice,CommunicationLog, Vendor, Campaign

class UsageChargeSerializer(serializers.ModelSerializer):
    cost = serializers.DecimalField(source='total_cost', max_digits=10, decimal_places=2, read_only=True)
    service_name = serializers.CharField(source='get_service_name_display', read_only=True)
    
    class Meta:
        model = UsageCharge
        fields = ['service_name', 'count', 'cost']

class PlatformChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformCharge
        fields = ['name', 'billing_cycle', 'cost']

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'date', 'amount', 'status', 'download_url']

class BillingDashboardSerializer(serializers.Serializer):
    period = serializers.CharField()    
    portal_usage_utilization_charges = UsageChargeSerializer(many=True) 
    platform_charges = PlatformChargeSerializer(many=True)
    invoices = InvoiceSerializer(many=True)
    total_usage_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_platform_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    grand_total = serializers.DecimalField(max_digits=10, decimal_places=2)

class StatsSummarySerializer(serializers.Serializer):
    sms_count = serializers.IntegerField()
    email_count = serializers.IntegerField()
    whatsapp_count = serializers.IntegerField()

class VendorCardSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    display_type = serializers.CharField(read_only=True) 
    
    # Main Stats
    total_communications = serializers.IntegerField(read_only=True)
    delivery_rate = serializers.FloatField(read_only=True)
    
    # Breakdown Stats
    delivered = serializers.IntegerField(read_only=True)
    failed = serializers.IntegerField(read_only=True)
    pending = serializers.IntegerField(read_only=True)
    
    # Financials & Status
    cost_per_message = serializers.DecimalField(max_digits=6, decimal_places=3, read_only=True)
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    last_activity = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)

# --- Serializer for the Bottom Table (Grouped Columns) ---
class VendorTableSerializer(serializers.Serializer):
    vendor_details = serializers.SerializerMethodField()
    type_label = serializers.CharField(source='display_type', read_only=True)
    total_communications = serializers.IntegerField(read_only=True)
    success_rate = serializers.SerializerMethodField()
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    contact_details = serializers.SerializerMethodField()

    def get_vendor_details(self, obj):
        return {
            "name": obj.get('name'),
            "vendor_id": obj.get('vendor_id')
        }

    def get_success_rate(self, obj):
        return {
            "rate": obj.get('delivery_rate'),
            "badge": obj.get('success_rate_label') 
        }

    def get_contact_details(self, obj):
        return {
            "name": obj.get('contact_name'),
            "email": obj.get('contact_email')
        }
        
class CommunicationLogSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    
    class Meta:
        model = CommunicationLog
        fields = ['id', 'customer_name', 'type', 'message_snippet', 'status', 'vendor_name', 'cost', 'timestamp']
class DeliveryStatusSerializer(serializers.ModelSerializer):
    # 1. Fetch 'case_number' from the related RenewalCase model
    case_id = serializers.CharField(source='case.case_number', default="-", read_only=True)

    # 2. Group Customer Name + Customer Code
    customer_details = serializers.SerializerMethodField()
    
    # 3. Format Type label (SMS, EMAIL)
    type_label = serializers.SerializerMethodField()
    
    # 4. Format Status (includes timestamp & error)
    status_details = serializers.SerializerMethodField()
    
    # 5. Vendor Name
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)

    class Meta:
        model = CommunicationLog
        fields = [
            'case_id', 
            'customer_details', 
            'type_label', 
            'message_snippet', 
            'status_details', 
            'attempts', 
            'vendor_name', 
            'cost'
        ]

    def get_customer_details(self, obj):
        # Access the related Customer object fields
        policy_id_display = "-"
        
        if obj.policy_chatbot:
            policy_id_display = obj.policy_chatbot.policy_id
        elif obj.customer:
            policy_id_display = obj.customer.customer_code

        if obj.customer:
            return {
                "name": obj.customer.full_name,      # Using property from Customer model
                "policy_id": policy_id_display
            }
        return {
            "name": "Unknown", 
            "policy_id": policy_id_display
        }

    def get_type_label(self, obj):
        return obj.type.upper() if obj.type else "UNKNOWN"

    def get_status_details(self, obj):
        return {
            "status": obj.status,
            "timestamp": obj.timestamp,
            "error_message": obj.error_message
        }
class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = '__all__'