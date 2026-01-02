from .models import DNCRegistry, DNCSettings
from django.db.models import Q

def is_allowed(contact, text_context=""):
    """
    The Master Logic:
    1. Scan for Renewal/Service keywords (Bypass DNC).
    2. Check if DNC checking is globally enabled in Settings.
    3. Check if the contact (Phone or Email) exists in the DNC Registry with 'Active' status.
    """
    
    # --- 1. SERVICE/RENEWAL BYPASS ---
    # We define keywords that indicate this is a service-related message.
    # If these words are found, we return True immediately (Allowing the contact).
    service_keywords = ['renewal', 'policy', 'expiry', 'expired', 'premium', 'due', 'urgent', 'reminder']
    context_lower = str(text_context).lower()
    
    if any(word in context_lower for word in service_keywords):
        # This is a renewal call/email; it should NOT be blocked by DNC.
        return True 

    # --- 2. GLOBAL TOGGLE CHECK ---
    # Check the singleton DNCSettings table.
    settings = DNCSettings.get_settings()
    if not settings.enable_checking:
        # If DNC checking is turned off globally, allow everything.
        return True

    # --- 3. DNC REGISTRY VERIFICATION ---
    # We check if the provided contact (phone or email) exists in the Registry.
    # We only block if the status is 'Active'.
    if not contact:
        return True # If no contact info is provided, we can't block it.

    is_blocked = DNCRegistry.objects.filter(
        (Q(phone_number=contact) | Q(email_address=contact)),
        status='Active'
    ).exists()

    # If is_blocked is True, we return False (Not Allowed).
    # If is_blocked is False, we return True (Allowed).
    return not is_blocked

def verify_customer_connection(contact_info):
    """
    Optional helper to verify which Customer and Client this contact belongs to.
    This can be used for logging purposes.
    """
    from apps.customers.models import Customer
    from apps.renewals.models import RenewalCase

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