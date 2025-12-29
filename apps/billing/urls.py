from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BillingViewSet, 
    InvoiceViewSet, 
    CommunicationStatsViewSet, 
    VendorStatsViewSet, 
    DeliveryStatusViewSet
)

router = DefaultRouter()
router.register(r'', BillingViewSet, basename='billing')
router.register(r'invoices', InvoiceViewSet, basename='invoices')
router.register(r'stats', CommunicationStatsViewSet, basename='stats')
router.register(r'vendors', VendorStatsViewSet, basename='vendors')
router.register(r'delivery', DeliveryStatusViewSet, basename='delivery')

urlpatterns = [
    path('', include(router.urls)),
]