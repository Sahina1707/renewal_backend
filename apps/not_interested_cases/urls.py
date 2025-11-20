from django.urls import path
from .views import NotInterestedCaseListAPIView

urlpatterns = [
    path('', NotInterestedCaseListAPIView.as_view(), name='api_not_interested_cases'),
]