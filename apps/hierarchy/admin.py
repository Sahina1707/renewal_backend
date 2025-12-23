from django.contrib import admin
from .models import Region, State, Branch, Department, Team

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'unit_name', 'manager', 'status')
    search_fields = ('unit_name', 'manager__email')
    list_filter = ('status',)

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    # 'region' is the Parent Unit here
    list_display = ('id', 'unit_name', 'region', 'manager', 'status')
    search_fields = ('unit_name', 'region__unit_name')
    list_filter = ('region', 'status')

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    # 'state' is the Parent Unit here
    list_display = ('id', 'unit_name', 'state', 'manager', 'status')
    search_fields = ('unit_name', 'state__unit_name')
    list_filter = ('state', 'status')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    # 'branch' is the Parent Unit here
    list_display = ('id', 'unit_name', 'branch', 'manager', 'status')
    search_fields = ('unit_name', 'branch__unit_name')
    list_filter = ('branch', 'status')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    # 'department' is the Parent Unit here
    list_display = ('id', 'unit_name', 'department', 'manager', 'status')
    search_fields = ('unit_name', 'department__unit_name')
    list_filter = ('department', 'status')