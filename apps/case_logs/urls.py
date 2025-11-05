from django.urls import path
from .views import (
    search_case_logs_by_case_number_api, search_case_logs_by_policy_number_api
)
from apps.case_tracking.views import update_case_log_api, edit_case_details_api

app_name = 'case_logs'

urlpatterns = [
    path('search/case-number/', search_case_logs_by_case_number_api, name='search-case-logs-by-case-number'),
    path('search/policy-number/', search_case_logs_by_policy_number_api, name='search-case-logs-by-policy-number'),
    path('update-case-log/<int:case_log_id>/', update_case_log_api, name='update-case-log'),
    path('case-details/edit/<int:case_id>/', edit_case_details_api, name='edit-case-details'),
]
