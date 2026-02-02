from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'customer_policy_preferences'

router = DefaultRouter()
router.register(r'', views.CustomerPolicyPreferenceViewSet, basename='customer-policy-preference')

urlpatterns = [
    path('', include(router.urls)),
]
