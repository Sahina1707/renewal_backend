from .models import DNCRegistry, DNCSettings
from django.db.models import Q
from apps.customers.models import Customer
from apps.renewals.models import RenewalCase

def is_allowed(contact, text_context=""):
    service_keywords = ['renewal', 'policy', 'expiry', 'expired', 'premium', 'due', 'urgent', 'reminder']
    context_lower = str(text_context).lower()
    
    if any(word in context_lower for word in service_keywords):
        return True 

    settings = DNCSettings.get_settings()
    if not settings.enable_checking:
        return True

    if not contact:
        return True 

    is_blocked = DNCRegistry.objects.filter(
        (Q(phone_number=contact) | Q(email_address=contact)),
        status='Active'
    ).exists()
    return not is_blocked

def verify_customer_connection(contact_info):
    try:
        customer = Customer.objects.filter(
            Q(phone_number=contact_info) | Q(email_address=contact_info)
        ).first()
        
        if customer:
            policy = RenewalCase.objects.filter(customer=customer).first()
            client_name = policy.distribution_channel.name if policy and policy.distribution_channel else "Unknown"
            return f"Customer: {customer.customer_name}, Client: {client_name}"
    except Exception:
        pass
    
    return "Unknown Contact"