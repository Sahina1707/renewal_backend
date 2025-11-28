from django.urls import path
from .views import LostCaseListAPIView
from .views import LostCaseUpdateAPIView

urlpatterns = [
    path('', LostCaseListAPIView.as_view(), name='api_lost_cases_list'),
    path('cases/<int:case_id>/mark-lost/', LostCaseUpdateAPIView.as_view()),
]