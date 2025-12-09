from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmailInboxMessageViewSet,
    EmailFolderViewSet,
    EmailConversationViewSet,
    EmailFilterViewSet,
    EmailAttachmentViewSet,
    EmailSearchQueryViewSet,
    BulkEmailCampaignViewSet,
    IncomingEmailWebhookAPIView
)

router = DefaultRouter()
router.register(r'messages', EmailInboxMessageViewSet, basename='email-inbox-message')
router.register(r'folders', EmailFolderViewSet, basename='email-folder')
router.register(r'conversations', EmailConversationViewSet, basename='email-conversation')
# router.register(r'filters', EmailFilterViewSet, basename='email-filter')
router.register(r'attachments', EmailAttachmentViewSet, basename='email-attachment')
router.register(r'search-queries', EmailSearchQueryViewSet, basename='email-search-query')
router.register(r'campaigns', BulkEmailCampaignViewSet, basename='bulk-email-campaign')
router.register(r'rules', EmailFilterViewSet, basename='email-filter')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/incoming-email/', IncomingEmailWebhookAPIView.as_view(), name='incoming-webhook'),
]
