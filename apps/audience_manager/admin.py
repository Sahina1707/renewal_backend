from django.contrib import admin
from .models import Audience, AudienceContact

@admin.register(Audience)
class AudienceAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_count', 'last_updated', 'is_deleted')
    list_filter = ('is_deleted', 'last_updated')
    search_fields = ('name',)

@admin.register(AudienceContact)
class AudienceContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'audience', 'is_deleted')
    list_filter = ('is_deleted', 'audience')
    search_fields = ('name', 'email', 'audience__name')
    raw_id_fields = ('audience',)
