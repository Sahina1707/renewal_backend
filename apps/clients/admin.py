from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "insurance_type",
        "contact_number",
        "email",
        "is_active",
        "created_at",
    )
    list_filter = ("insurance_type", "is_active")
    search_fields = ("name", "code", "email")
