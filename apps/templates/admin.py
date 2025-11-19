from django.contrib import admin
from .models import Template

@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Template model.
    """
    list_display = ('name', 'channel', 'category', 'is_dlt_approved', 'is_active', 'updated_at')
    list_filter = ('channel', 'category', 'is_dlt_approved', 'is_active')
    search_fields = ('name', 'subject', 'content', 'dlt_template_id')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'channel', 'template_type', 'category', 'is_active')
        }),
        ('Content', {
            'fields': ('subject', 'content', 'variables')
        }),
        ('Provider (Twilio/DLT)', {
            'fields': ('dlt_template_id', 'is_dlt_approved', 'tags')
        }),
    )
    
    # This makes it easier to edit the 'variables' and 'tags' JSON fields
    # (though they will still just be text boxes)
    readonly_fields = ('created_at', 'updated_at', 'created_by')