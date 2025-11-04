"""
URLs for Outstanding Amounts functionality
"""

from django.urls import path
from .views import (
    get_outstanding_summary_api,
    initiate_payment_api,
    setup_payment_plan_api
)

app_name = 'outstanding_amounts'

urlpatterns = [
    path(
        'cases/outstanding-amounts/summary/<str:case_id>/',
        get_outstanding_summary_api,
        name='get-outstanding-summary'
    ),
    
    path(
        'cases/outstanding-amounts/pay/<str:case_id>/',
        initiate_payment_api,
        name='initiate-payment'
    ),
    
    path(
        'cases/outstanding-amounts/setup-payment-plan/<str:case_id>/',
        setup_payment_plan_api,
        name='setup-payment-plan'
    ),
]
