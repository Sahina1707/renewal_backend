from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CaseLogViewSet, update_case_log_api, comment_history_api,
    get_case_details_api, edit_case_details_api, get_case_edit_form_data_api,
    get_policy_types_dropdown_api, get_agents_dropdown_api,
    search_case_logs_by_case_number_api, search_case_logs_by_policy_number_api
)

router = DefaultRouter()
router.register(r'case-logs', CaseLogViewSet, basename='case-logs')

app_name = 'case_logs'

urlpatterns = [
    path('', include(router.urls)),
    path('update-case-log/<int:case_id>/', update_case_log_api, name='update-case-log'),
    path('comment-history/<int:case_id>/', comment_history_api, name='comment-history-api'),

    path('comment-history-formatted/<int:case_id>/', CaseLogViewSet.as_view({'get': 'comment_history'}), name='case-logs-comment-history-formatted'),

    path('case-details/<int:case_id>/', get_case_details_api, name='get-case-details'),
    path('case-details/edit/<int:case_id>/', edit_case_details_api, name='edit-case-details'),
    path('case-edit-form-data/<int:case_id>/', get_case_edit_form_data_api, name='get-case-edit-form-data'),

    path('case-details/policy-types/', get_policy_types_dropdown_api, name='get-policy-types-dropdown'),
    path('case-details/agents/', get_agents_dropdown_api, name='get-agents-dropdown'),

    # Search APIs
    path('search/case-number/', search_case_logs_by_case_number_api, name='search-case-logs-by-case-number'),
    path('search/policy-number/', search_case_logs_by_policy_number_api, name='search-case-logs-by-policy-number'),
]
