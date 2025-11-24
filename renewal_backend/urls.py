"""
URL configuration for Intelipro Insurance Policy Renewal System.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes
from django.http import JsonResponse

# Public schema view (allow docs without auth)
class PublicSchemaView(SpectacularAPIView):
    permission_classes = [AllowAny]

# API URL patterns
api_patterns = [
    # Authentication endpoints
    path('auth/', include('apps.authentication.urls')),

    # Core utilities
    path('core/', include('apps.core.urls')),

    # User management
    path('users/', include('apps.users.urls')),

    # Core business endpoints
    path('customers/', include('apps.customers.urls')),
    path('policies/', include('apps.policies.urls')),
    path('campaigns/', include('apps.campaigns.urls')),
    path('audience_manager/',include('apps.audience_manager.urls')),
    path('templates/', include('apps.templates.urls')),
    path('policy_data/', include('apps.policy_data.urls')),
    path('files_upload/', include('apps.files_upload.urls')),
    path('channels/', include('apps.channels.urls')),
    path('distribution-channels/', include('apps.distribution_channel.urls')),
    path('hierarchy/', include('apps.hierarchy.urls')),
    path('case-tracking/', include('apps.case_tracking.urls')),
    path('case-logs/', include('apps.case_logs.urls')),
    path('case-details/', include('apps.case_details.urls')),
    path('cases/', include('apps.case_history.urls')),
    path('closed-cases/', include('apps.closed_cases.urls')),
    path('not-interested-cases/', include('apps.not_interested_cases.urls')),
    path('archived-cases/', include('apps.archived_cases.urls')),
    path('lost-cases/', include('apps.lost_cases.urls')),
    path('whatsapp-manager/',include('apps.whatsapp_manager.urls')),
    path('financial-profiles/', include('apps.customer_financial_profile.urls')),
    path('customer-assets/', include('apps.customer_assets.urls')),
    path('customer-vehicles/', include('apps.customer_vehicle.urls')),
    path('customer-policy-preferences/', include('apps.customer_policy_preferences.urls')),
    path('customer-family-medical-history/', include('apps.customer_family_medical_history.urls')),
    path('customer-payments/', include('apps.customer_payments.urls')),
    path('customer-payment-schedule/', include('apps.customer_payment_schedule.urls')),
    path('customer-communication-preferences/', include('apps.customer_communication_preferences.urls')),
    path('customer-installments/', include('apps.customer_installment.urls')),
    path('customers-files/', include('apps.customers_files.urls')),
    path('customer-insights/', include('apps.customer_insights.urls')),
    path('claims/', include('apps.claims.urls')),
    path('campaign_manager/',include('apps.campaign_manager.urls')),
    path('sms_provider/',include('apps.sms_provider.urls')),
    path('target-audience/', include('apps.target_audience.urls')),
    path('policy-timeline/', include('apps.policy_timeline.urls')),
    path('renewal-timeline/', include('apps.renewal_timeline.urls')),
    path('other-insurance-policies/', include('apps.other_insurance_policies.urls')),
    path('policy-features/', include('apps.policy_features.urls')),
    path('policy-additional-benefits/', include('apps.policy_additional_benefits.urls')),
    path('policy-coverages/', include('apps.policy_coverages.urls')),
    path('policy-exclusions/', include('apps.policy_exclusions.urls')),
    path('policy-conditions/', include('apps.policy_conditions.urls')),
    path("teams/", include("apps.teams.urls")),

    # Email Integration endpoints
    path('email-provider/', include('apps.email_provider.urls')),
    # path('communication-provider/', include('apps.communication_provider.urls')),  
    path('email-templates/', include('apps.email_templates.urls')),
    path('email-operations/', include('apps.email_operations.urls')),
    path('email-inbox/', include('apps.email_inbox.urls')),
    path('email-integration/', include('apps.email_integration.urls')),
    path('email-manager/', include('apps.email_manager.urls')),

    # WhatsApp Integration endpoints
    path('whatsapp_provider/', include('apps.whatsapp_provider.urls')),
    path('offers/', include('apps.offers.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('upload-chatbot/', include('apps.upload_chatbot.urls')),
    path('case-tracking-chatbot/', include('apps.case_tracking_chatbot.urls')),
    path('closed-case-chatbot/', include('apps.closed_case_chatbot.urls')),
    path('policy-timeline-chatbot/', include('apps.policytimeline_chatbot.urls')),
    path('case-logs-chatbot/', include('apps.case_logs_chatbot.urls')),
    
    # Customer Verification endpoints
    path('verification/', include('apps.verification.urls')),

    # API Documentation
    path('schema/', PublicSchemaView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Main URL patterns
urlpatterns = [
    # Admin interface
    path(f'{settings.ADMIN_URL if hasattr(settings, "ADMIN_URL") else "admin/"}', admin.site.urls),
    
    # API endpoints
    path('api/', include(api_patterns)),
    
    # Health check endpoint (simple one for now)
    path('health/', lambda request: JsonResponse({'status': 'healthy'})),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Add debug toolbar URLs
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

# Custom error handlers
handler400 = 'apps.core.views.bad_request'
handler403 = 'apps.core.views.permission_denied'
handler404 = 'apps.core.views.page_not_found'
handler500 = 'apps.core.views.server_error'

# Admin site customization
admin.site.site_header = 'Intelipro Insurance Renewal System'
admin.site.site_title = 'Intelipro Admin'
admin.site.index_title = 'Administration Dashboard' 
