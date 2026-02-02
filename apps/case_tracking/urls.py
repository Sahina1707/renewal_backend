from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CaseTrackingViewSet, update_case_log_api, comment_history_api,
    get_case_details_api, edit_case_details_api, get_case_edit_form_data_api,
    get_policy_types_dropdown_api, get_agents_dropdown_api
)

router = DefaultRouter()
router.register(r'cases', CaseTrackingViewSet, basename='case-tracking')

app_name = 'case_tracking'

urlpatterns = [
    path('', include(router.urls)),

    path('update-case-log/<int:case_id>/', update_case_log_api, name='update-case-log'),
    path('comment-history/<int:case_id>/', comment_history_api, name='comment-history-api'),

    path('case-details/<int:case_id>/', get_case_details_api, name='get-case-details'),
    path('case-details/edit/<int:case_id>/', edit_case_details_api, name='edit-case-details'),
    path('case-edit-form-data/<int:case_id>/', get_case_edit_form_data_api, name='get-case-edit-form-data'),

    path('case-details/policy-types/', get_policy_types_dropdown_api, name='get-policy-types-dropdown'),
    path('case-details/agents/', get_agents_dropdown_api, name='get-agents-dropdown'),

    # include outstanding amounts URLs
    path('', include('apps.outstanding_amounts.urls')),
]
