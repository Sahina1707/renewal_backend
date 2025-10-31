from django.contrib import admin
from django.utils.html import format_html
from .models import EmailTemplate, EmailTemplateTag, EmailTemplateVersion


@admin.register(EmailTemplateTag)
class EmailTemplateTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display', 'is_active', 'template_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def color_display(self, obj):
        """Display color as a colored square"""
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;"></span> {}',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def template_count(self, obj):
        """Count of templates with this tag"""
        return obj.templates.filter(is_deleted=False).count()
    template_count.short_description = 'Templates'
    
    def get_queryset(self, request):
        """Filter out soft-deleted tags"""
        return super().get_queryset(request).filter(is_deleted=False)


class EmailTemplateVersionInline(admin.TabularInline):
    model = EmailTemplateVersion
    extra = 0
    readonly_fields = ['version_number', 'created_at', 'created_by']
    fields = ['version_number', 'name', 'subject', 'template_type', 'is_current', 'created_at', 'created_by']


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'subject', 'status', 'template_type',
        'usage_count', 'is_public', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'template_type', 'is_public', 'created_at']
    search_fields = ['name', 'subject', 'description']
    readonly_fields = [
        'id', 'usage_count', 'last_used', 'created_at', 'updated_at',
        'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by'
    ]
    filter_horizontal = ['tags']
    inlines = [EmailTemplateVersionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'subject', 'description', 'tags')
        }),
        ('Content', {
            'fields': ('html_content', 'text_content', 'template_type', 'variables')
        }),
        ('Settings', {
            'fields': ('status', 'is_default', 'is_public')
        }),
        ('Usage Tracking', {
            'fields': ('usage_count', 'last_used'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Filter out soft-deleted templates"""
        return super().get_queryset(request).filter(is_deleted=False)
    
    actions = ['activate_templates', 'deactivate_templates', 'archive_templates']
    
    def activate_templates(self, request, queryset):
        """Activate selected templates"""
        count = queryset.update(status='active')
        self.message_user(request, f"{count} templates activated successfully.")
    activate_templates.short_description = "Activate selected templates"
    
    def deactivate_templates(self, request, queryset):
        """Deactivate selected templates"""
        count = queryset.update(status='inactive')
        self.message_user(request, f"{count} templates deactivated successfully.")
    deactivate_templates.short_description = "Deactivate selected templates"
    
    def archive_templates(self, request, queryset):
        """Archive selected templates"""
        count = queryset.update(status='archived')
        self.message_user(request, f"{count} templates archived successfully.")
    archive_templates.short_description = "Archive selected templates"


@admin.register(EmailTemplateVersion)
class EmailTemplateVersionAdmin(admin.ModelAdmin):
    list_display = [
        'template', 'version_number', 'name', 'subject', 'template_type',
        'is_current', 'created_at', 'created_by'
    ]
    list_filter = ['template_type', 'is_current', 'created_at', 'template']
    search_fields = ['template__name', 'name', 'subject', 'change_summary']
    readonly_fields = ['id', 'version_number', 'created_at', 'created_by']
    
    fieldsets = (
        ('Version Information', {
            'fields': ('template', 'version_number', 'is_current', 'change_summary')
        }),
        ('Content', {
            'fields': ('name', 'subject', 'html_content', 'text_content', 'template_type', 'variables')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('template', 'created_by')
