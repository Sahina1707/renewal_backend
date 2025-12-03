from django.urls import path
from .views import NotInterestedCaseListAPIView
from .views import NotInterestedCaseUpdateAPIView

urlpatterns = [
    path('', NotInterestedCaseListAPIView.as_view(), name='api_not_interested_cases'),
    path('cases/<int:case_id>/mark-not-interested/', NotInterestedCaseUpdateAPIView.as_view()),
]