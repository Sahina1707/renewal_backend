from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClosedCasesViewSet, 
    ClosedCasesCombinedDataAPIView, 
    ClosedCasesPreferencesSummaryAPIView, 
    ClosedCasesPolicyMembersAPIView, 
    ClosedCasesOffersAPIView,
    closed_cases_timeline_view,
    ClosedCasesCommentListView,
    ClosedCasesCommentDetailView,
    ClosedCasesUpdateStatusView,
    get_closed_case_outstanding_summary_api,
    get_closed_case_customer_insights_api,
    get_closed_case_communication_history_api,
    get_closed_case_claims_history_api
)

router = DefaultRouter()
router.register(r'closed-cases', ClosedCasesViewSet, basename='closed-cases')

app_name = 'closed_cases'

urlpatterns = [
    path('', include(router.urls)),
    path('combined-policy-data/<str:case_number>/', ClosedCasesCombinedDataAPIView.as_view(), name='closed_cases_combined_data'),
    path('preferences-summary/<str:case_ref>/', ClosedCasesPreferencesSummaryAPIView.as_view(), name='closed_cases_preferences_summary'),
    path('members/by-case/<str:case_id>/', ClosedCasesPolicyMembersAPIView.as_view(), name='closed_cases_policy_members'),
    path('offers/for-case/<str:case_id>/', ClosedCasesOffersAPIView.as_view(), name='closed_cases_offers'),
    path('timeline/<str:case_number>/', closed_cases_timeline_view, name='closed_cases_timeline'),
    path('comments/<str:case_number>/', ClosedCasesCommentListView.as_view(), name='closed_cases_comment_list'),
    path('comments/<str:case_number>/<int:pk>/', ClosedCasesCommentDetailView.as_view(), name='closed_cases_comment_detail'),
    path('update-status/<str:case_number>/', ClosedCasesUpdateStatusView.as_view(), name='closed_cases_update_status'),
    path('cases/outstanding-amounts/summary/<str:case_id>/', get_closed_case_outstanding_summary_api, name='closed_cases_outstanding_summary'),
    path('customer/<str:case_number>/', get_closed_case_customer_insights_api, name='closed_cases_customer_insights'),
    path('customer/communication-history/<str:case_number>/', get_closed_case_communication_history_api, name='closed_cases_communication_history'),
    path('customer/claims-history/<str:case_number>/', get_closed_case_claims_history_api, name='closed_cases_claims_history'),
]
