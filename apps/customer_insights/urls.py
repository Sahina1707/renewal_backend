"""
URL configuration for Customer Insights app.
Simplified design with consolidated endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerInsightsViewSet


router = DefaultRouter()
router.register(r'insights', CustomerInsightsViewSet, basename='customer-insights')

app_name = 'customer_insights'

urlpatterns = [
    # Main insights endpoint - consolidated (accepts case_number like CASE-001)
    path('customer/<str:case_number>/', 
         CustomerInsightsViewSet.as_view({'get': 'get_customer_insights'}), 
         name='customer-insights'),
    
    # Recalculate insights (accepts case_number like CASE-001)
    path('customer/<str:case_number>/recalculate/', 
         CustomerInsightsViewSet.as_view({'post': 'recalculate_insights'}), 
         name='customer-insights-recalculate'),
    
    # Payment schedule endpoint (accepts customer_id)
    path('customer/<int:customer_id>/payment-schedule/', 
         CustomerInsightsViewSet.as_view({'get': 'get_payment_schedule'}), 
         name='customer-payment-schedule'),
    
    # Dashboard and summary endpoints
    path('dashboard/', 
         CustomerInsightsViewSet.as_view({'get': 'get_insights_dashboard'}), 
         name='insights-dashboard'),
    
    path('summary/', 
         CustomerInsightsViewSet.as_view({'get': 'get_insights_summary'}), 
         name='insights-summary'),
    
    # Bulk operations
    path('bulk-update/', 
         CustomerInsightsViewSet.as_view({'post': 'bulk_update_insights'}), 
         name='bulk-update-insights'),
    
    # Include router URLs for CRUD operations
    path('', include(router.urls)),
]
