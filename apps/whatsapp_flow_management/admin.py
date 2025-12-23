from django.contrib import admin
from .models import WhatsAppFlow, FlowBlock, FlowAnalytics, WhatsAppMessageTemplate, FlowTemplate

class FlowBlockInline(admin.TabularInline):
    model = FlowBlock
    extra = 0

@admin.register(WhatsAppFlow)
class WhatsAppFlowAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'entry_point', 'created_at', 'is_deleted')
    inlines = [FlowBlockInline]

@admin.register(WhatsAppMessageTemplate)
class WhatsAppMessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at')

@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')

admin.site.register(FlowAnalytics)