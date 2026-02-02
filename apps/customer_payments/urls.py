from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'customer_payments'

router = DefaultRouter()
router.register(r'payments', views.CustomerPaymentViewSet, basename='customer-payment')

urlpatterns = [

    path('', include(router.urls)),
]
