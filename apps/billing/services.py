from decimal import Decimal
from django.utils import timezone
from .models import CommunicationLog, Vendor, BillingPeriod, UsageCharge

def log_communication(
    vendor_name, 
    service_type, 
    customer=None, 
    case=None, 
    status='pending', 
    cost=None, 
    error_message=None,
    message_snippet=None,
    provider_message_id=None
):
    """
    Central logging function. Call this from apps/sms, apps/email, etc.
    
    :param cost: The REAL cost returned by the provider API (e.g., Twilio price). 
                 If None, falls back to Vendor.cost_per_message.
    """
    # 1. Find or Create the Vendor
    # This auto-registers new vendors (e.g., 'Twilio', 'SendGrid') on the fly.
    vendor, _ = Vendor.objects.get_or_create(
        name=vendor_name, 
        defaults={
            'service_type': service_type,
            'contact_name': 'System',
            'contact_email': 'admin@system.com',
            'cost_per_message': 0.00  
        }
    )
    final_cost = Decimal(str(cost)) if cost is not None else vendor.cost_per_message
    cust_name = customer.full_name if customer else "Unknown"
    snippet = message_snippet if message_snippet else f"Sent via {vendor_name}"

    CommunicationLog.objects.create(
        vendor=vendor,
        customer=customer,
        case=case,
        type=service_type,
        status=status,
        cost=final_cost,
        error_message=error_message,
        timestamp=timezone.now(),
        message_snippet=snippet,
        customer_name=cust_name,
        provider_message_id=provider_message_id
    )

    # 4. Update Aggregated Usage (For the "Billing Details" Tab)
    today = timezone.now().date()
    period, _ = BillingPeriod.objects.get_or_create(
        month=today.month,
        year=today.year,
        defaults={'is_active': True}
    )

    usage_charge, _ = UsageCharge.objects.get_or_create(
        period=period,
        service_name=service_type,
        defaults={
            'rate_per_unit': 0.00, 
            'count': 0
        }
    )
    
    # Calculate Running Average for Rate to ensure Total Cost is accurate
    # Current Total + New Cost = New Total
    current_total_cost = usage_charge.count * usage_charge.rate_per_unit
    new_total_cost = current_total_cost + final_cost
    
    usage_charge.count += 1
    usage_charge.rate_per_unit = new_total_cost / usage_charge.count
    usage_charge.save()