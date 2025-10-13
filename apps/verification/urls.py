from django.urls import path
from . import views

app_name = 'verification'

urlpatterns = [
    path('verify/', views.verify_customer_data, name='verify_customer_data'),
    path('status/<int:customer_id>/', views.get_customer_verification_status, name='customer_verification_status'),
    path('bulk-verify/', views.bulk_verify_customers, name='bulk_verify_customers'),
    path('verify-pan-document/', views.verify_pan_with_document, name='verify_pan_with_document'),
]
