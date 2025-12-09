from django.urls import path
from . import views

urlpatterns = [
    path('provider-options/', views.ProviderOptionsView.as_view(), name='provider-options'),
    path('settings/', views.CampaignSettingsView.as_view(), name='campaign-settings'),
    path('download-report/', views.DownloadReportView.as_view(), name='download-report'),

]