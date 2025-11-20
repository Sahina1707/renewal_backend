from django.urls import path
from .views import LostCaseListAPIView

urlpatterns = [
    path('', LostCaseListAPIView.as_view(), name='api_lost_cases_list'),
]