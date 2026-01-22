from datetime import date, timedelta
from django.utils import timezone
from .models import RenewalCase
from apps.customer_payments.models import CustomerPayment
from apps.policies.models import Policy
from apps.renewal_settings.models import RenewalSettings
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


def refresh_all_cases():
    today = date.today()

    # 1) Auto-expire cases
    RenewalCase.objects.filter(
        status__in=["pending", "assigned", "in_progress"],
        policy__end_date__lt=today
    ).update(status="expired")

    # 2) Sync payment status (✅ FIXED HERE)
    paid_case_ids = CustomerPayment.objects.filter(
        payment_status="success",
        renewal_cases__isnull=False
    ).values_list("renewal_cases__id", flat=True)

    RenewalCase.objects.filter(
        id__in=paid_case_ids
    ).update(payment_status="success")

    # 3) Auto archive expired cases
    RenewalCase.objects.filter(
        status="expired",
        is_archived=False
    ).update(
        is_archived=True,
        archived_date=today
    )

    # 4) Clear follow-ups
    RenewalCase.objects.filter(
        status="expired"
    ).update(
        follow_up_date=None,
        follow_up_time=None
    )

    # 5) Auto-Create Renewal Cases (Start of Renewal Process)
    # Added for Policy Processing Settings (Slider & Auto-Assign)
    try:
        settings_obj = RenewalSettings.objects.first()
        if settings_obj and settings_obj.default_renewal_period:
            period_days = settings_obj.default_renewal_period
            auto_assign = settings_obj.auto_assign_cases
            
            # Calculate target expiry date (Today + X Days)
            target_date = today + timedelta(days=period_days)
            
            # Find Active Policies expiring exactly on this date
            # We use exact match to avoid reprocessing, assuming this runs daily.
            candidates = Policy.objects.filter(
                policy_end_date=target_date,
                status='active'
            ).exclude(
                renewal_cases__isnull=False
            )
            
            # Prepare Agents for Round-Robin if enabled
            agents = []
            if auto_assign:
                # Get active staff/agents
                agents = list(User.objects.filter(is_active=True, is_staff=True))
            
            agent_count = len(agents)
            agent_idx = 0
            
            for policy in candidates:
                try:
                    with transaction.atomic():
                        # Create unique case number
                        # Format: RC-{PolicyID}-{Date}
                        case_num = f"RC-{policy.policy_number}-{timezone.now().strftime('%Y%m%d')}"
                        
                        # Create Case
                        case = RenewalCase.objects.create(
                            case_number=case_num,
                            policy=policy,
                            customer=policy.customer, # Assuming policy has customer FK
                            status='pending' if not auto_assign else 'assigned',
                            renewal_amount=policy.premium_amount,
                            priority='medium'
                        )
                        
                        # Assign Agent
                        if auto_assign and agent_count > 0:
                            selected_agent = agents[agent_idx % agent_count]
                            case.assigned_to = selected_agent
                            case.save()
                            agent_idx += 1
                            
                except Exception as e:
                    print(f"Error creating auto-renewal case for policy {policy.id}: {e}")
                    
    except Exception as setting_error:
        print(f"Error in Step 5 (Auto-Create): {setting_error}")
