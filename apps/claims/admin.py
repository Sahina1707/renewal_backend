from django.contrib import admin
from .models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = [
        'claim_number',
        'customer',
        'policy_number',
        'claim_type',
        'claim_amount',
        'status',
        'insurance_company_name',
        'created_at',
    ]
    list_filter = ['status', 'claim_type', 'created_at']
    search_fields = [
        'claim_number',
        'customer__first_name',
        'customer__last_name',
        'customer__email',
        'policy_number',
        'insurance_company_name',
    ]
    readonly_fields = ['claim_number', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('claim_number', 'customer', 'policy', 'policy_number')
        }),
        ('Claim Details', {
            'fields': (
                'insurance_company_name',
                'expire_date',
                'claim_type',
                'claim_amount',
                'description',
                'status',
                'remarks',
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
