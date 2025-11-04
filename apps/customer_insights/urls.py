"""
URL configuration for Customer Insights app.
Simplified design with consolidated endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerInsightsViewSet


router = DefaultRouter()
router.register(r'customer_insights', CustomerInsightsViewSet, basename='customer-insights')

app_name = 'customer_insights'

urlpatterns = [
    path('customer/<str:case_number>/', 
         CustomerInsightsViewSet.as_view({'get': 'get_customer_insights'}), 
         name='customer-insights'),
    
    path('customer/recalculate/<str:case_number>/', 
         CustomerInsightsViewSet.as_view({'post': 'recalculate_insights'}), 
         name='customer-insights-recalculate'),
    
    path('customer/payment-schedule/<int:customer_id>/', 
         CustomerInsightsViewSet.as_view({'get': 'get_payment_schedule'}), 
         name='customer-payment-schedule'),
    
    path('customer/communication-history/<str:case_number>/',
         CustomerInsightsViewSet.as_view({'get': 'get_communication_history_detail'}),
         name='customer-communication-history'),

    path('customer/claims-history/<str:case_number>/',
         CustomerInsightsViewSet.as_view({'get': 'get_claims_history_detail'}),
         name='customer-claims-history'),
    
    path('dashboard/', 
         CustomerInsightsViewSet.as_view({'get': 'get_insights_dashboard'}), 
         name='insights-dashboard'),
    
    path('summary/', 
         CustomerInsightsViewSet.as_view({'get': 'get_insights_summary'}), 
         name='insights-summary'),
    
    path('bulk-update/', 
         CustomerInsightsViewSet.as_view({'post': 'bulk_update_insights'}), 
         name='bulk-update-insights'),
    
    path('', include(router.urls)),
]
