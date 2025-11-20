from django.urls import path
from .views import ArchivedCaseListAPIView, ArchiveCasesView, UnarchiveCasesView

urlpatterns = [
    # The Dashboard Page (GET)
    path('', ArchivedCaseListAPIView.as_view(), name='api_archived_cases_list'),
    
    # The Actions (POST)
    path('archive/', ArchiveCasesView.as_view(), name='api_archive_cases'),
    path('unarchive/', UnarchiveCasesView.as_view(), name='api_unarchive_cases'),
]