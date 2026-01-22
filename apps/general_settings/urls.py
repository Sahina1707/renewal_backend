from django.urls import path
from .views import GeneralSettingsViewSet, MFAViewSet

urlpatterns = [
    path('my_settings/', GeneralSettingsViewSet.as_view({'get': 'my_settings', 'patch': 'my_settings'}), name='my-settings'),    
    path('mfa/generate/', MFAViewSet.as_view({'get': 'generate_qr'}), name='mfa-generate'),
    path('mfa/verify/', MFAViewSet.as_view({'post': 'verify_and_enable'}), name='mfa-verify'),
    path('mfa/disable/', MFAViewSet.as_view({'post': 'disable'}), name='mfa-disable'),
]