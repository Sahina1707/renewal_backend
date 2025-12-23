from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (EmailAccountViewSet, ClassificationRuleViewSet, EmailModuleSettingsAPIView,TestConnectionAPIView,ProviderDefaultsAPIView,
    GlobalTestConnectionAPIView,ManualSyncAPIView)

# Create a router and register our ViewSets with it.
router = DefaultRouter()
router.register(r'email-accounts', EmailAccountViewSet, basename='emailaccount')
router.register(r'classification-rules', ClassificationRuleViewSet, basename='classificationrule')

urlpatterns = [
    # Router URLs for Email Accounts and Classification Rules (e.g., /settings/email-accounts/1/)
    path('', include(router.urls)),
    
    # Custom URL for the singleton Email Module Settings (e.g., /settings/general/)
    path('general/', EmailModuleSettingsAPIView.as_view(), name='general-settings'),
    path('email-accounts/<int:pk>/test-connection/', TestConnectionAPIView.as_view(), name='email-account-test-connection'),
    path('email-accounts/<int:pk>/sync-now/', ManualSyncAPIView.as_view(), name='manual-sync'),
    path('providers/defaults/', ProviderDefaultsAPIView.as_view(), name='provider-defaults'),
    path('test-global-connection/', GlobalTestConnectionAPIView.as_view(), name='global-test-connection'),
]

