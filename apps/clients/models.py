from django.db import models
from django.db.models import Q
from apps.core.models import BaseModel


class Client(BaseModel):

    INSURANCE_TYPES = [
        ("life", "Life Insurance"),
        ("health", "Health Insurance"),
        ("motor", "Motor Insurance"),
        ("home", "Home Insurance"),
        ("car", "Car Insurance"),
    ]

    # ❌ DO NOT use unique=True here
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)

    insurance_type = models.CharField(
        max_length=20,
        choices=INSURANCE_TYPES
    )

    description = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # ✅ Only ONE active (not deleted) client
            models.UniqueConstraint(
                fields=["name", "code"],
                condition=Q(is_deleted=False),
                name="unique_active_client_name_code"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"
