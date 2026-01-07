from django.urls import path
from .views import (
    RenewalSettingsView, 
    RenewalSettingsDetailView, 
    QuickMessageSettingsView,
    TestCallIntegrationView,
    TestSmsIntegrationView,
    TestWhatsAppIntegrationView,
    PolicySettingsView,
    AutoRefreshSettingsView, 
    CallIntegrationGlobalView,
    IntegrationSettingsView
)
from .quick_views import QuickMessageSendView

urlpatterns = [
    # 1. General URL (Master GET)
    path('', RenewalSettingsView.as_view(), name='renewal-settings-list'),
    
    # 1.1 Auto Refresh & Edit UI
    path('auto-refresh/', AutoRefreshSettingsView.as_view(), name='auto-refresh-settings'),
    
    # 1.2 Policy Processing Settings
    path('policy-processing/', PolicySettingsView.as_view(), name='policy-settings'),
    
    # 1.3 Call Integration Global
    path('call-integration/', CallIntegrationGlobalView.as_view(), name='call-integration-global'),
    path('call-integration/<int:provider_id>/', RenewalSettingsDetailView.as_view(), name='call-integration-detail'),
    
    # 1.4 Integration Settings Status (Connection Check)
    path('integration-settings/', IntegrationSettingsView.as_view(), name='integration-settings'),

    # 2. Specific ID URL (Edit specific provider features)
    # Example: http://127.0.0.1:8000/renewal-settings/9/
    path('<int:provider_id>/', RenewalSettingsDetailView.as_view(), name='renewal-settings-detail'),

    # 3. Quick Message Settings (Singleton)
    # Example: http://127.0.0.1:8000/renewal-settings/quick-message-settings/
    path('quick-message-settings/', QuickMessageSettingsView.as_view(), name='quick-message-settings'),
    path('quick-messages/send/', QuickMessageSendView.as_view(), name='send-quick-message'),

    # 4. Integration Testing Endpoints
    path('test-integration/call/', TestCallIntegrationView.as_view(), name='test-call-integration'),
    path('test-integration/sms/', TestSmsIntegrationView.as_view(), name='test-sms-integration'),
    path('test-integration/whatsapp/', TestWhatsAppIntegrationView.as_view(), name='test-whatsapp-integration'),
]