

from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('health/detailed/', views.detailed_health_check, name='detailed_health_check'),
    
    path('system/info/', views.system_info, name='system_info'),
    path('system/status/', views.system_status, name='system_status'),
    
    path('config/', views.system_config, name='system_config'),
    path('config/<str:category>/', views.system_config_by_category, name='system_config_by_category'),
    
    path('audit/', views.audit_logs, name='audit_logs'),
] 