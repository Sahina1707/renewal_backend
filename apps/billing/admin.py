from django.contrib import admin
from .models import BillingPeriod, UsageCharge, PlatformCharge, Invoice
@admin.register(BillingPeriod)
class BillingPeriodAdmin(admin.ModelAdmin):
    list_display = ('month', 'year', 'is_active')
    list_filter = ('year',)
@admin.register(UsageCharge)
class UsageChargeAdmin(admin.ModelAdmin):
    list_display = ('period', 'service_name', 'count', 'total_cost')
    readonly_fields = ('total_cost',) 

@admin.register(PlatformCharge)
class PlatformChargeAdmin(admin.ModelAdmin):
    list_display = ('name', 'cost', 'billing_cycle', 'period')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'date', 'amount', 'status')
    list_filter = ('status',)