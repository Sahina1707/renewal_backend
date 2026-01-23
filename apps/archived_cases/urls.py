from django.urls import path
from .views import ArchivedCaseListAPIView, ArchiveCasesView, UnarchiveCasesView, ArchiveSingleCaseAPIView

urlpatterns = [
    path('', ArchivedCaseListAPIView.as_view(), name='api_archived_cases_list'),
    path('archive/', ArchiveCasesView.as_view(), name='api_archive_cases'),
    path('unarchive/', UnarchiveCasesView.as_view(), name='api_unarchive_cases'),
    path('cases/<int:case_id>/archive/', ArchiveSingleCaseAPIView.as_view(),name='api_archive_single_case'),
]