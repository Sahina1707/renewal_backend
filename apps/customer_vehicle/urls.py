from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'customer_vehicle'

router = DefaultRouter()
router.register(r'', views.CustomerVehicleViewSet, basename='customer-vehicle')

urlpatterns = [
    path('', include(router.urls)),
]
