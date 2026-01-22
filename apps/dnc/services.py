from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import DNCSettings, DNCRegistry, DNCOverrideLog


def evaluate_dnc(
    *,
    phone_number: str,
    user=None,
    request_override: bool = False,
    source: str = "dnc",
    reason: str = None,
):
    """
    Core DNC decision engine.

    Enforces:
    - Block DNC Contacts
    - Universal Allow DNC Overrides switch

    Does NOT:
    - Auto-check before sending
    - Intercept other apps
    """

    settings = DNCSettings.get_settings()

    # 1️⃣ Master switch
    if not settings.enable_dnc_checking:
        return {
            "allowed": True,
            "blocked": False,
            "override_used": False,
            "message": "DNC checking disabled",
        }

    # 2️⃣ Check registry
    dnc_entry = DNCRegistry.objects.filter(
        phone_number=phone_number,
        status="Active",
    ).first()

    if not dnc_entry:
        return {
            "allowed": True,
            "blocked": False,
            "override_used": False,
            "message": "Not in DNC registry",
        }

    # 3️⃣ Block DNC Contacts
    if not settings.block_dnc_contacts:
        return {
            "allowed": True,
            "blocked": False,
            "override_used": False,
            "message": "Blocking disabled",
        }

    # 4️⃣ Universal override gate
    if request_override:
        if not settings.allow_dnc_overrides:
            raise PermissionDenied("DNC override is disabled globally")

        if not dnc_entry.allow_override_requests:
            raise PermissionDenied("Override not allowed for this DNC entry")

        if not user:
            raise PermissionDenied("User required for override")

        DNCOverrideLog.objects.create(
            dnc_entry=dnc_entry,
            override_type="Manual Override",
            reason=reason or "Manual override",
            authorized_by=(
                user.username or user.email or str(user.id)
            ),
            created_at=timezone.now(),
        )

        return {
            "allowed": True,
            "blocked": False,
            "override_used": True,
            "message": "Override approved",
        }

    # 5️⃣ Hard block
    raise PermissionDenied("Number is blocked by DNC")
