from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import EmailManagerViewSet, EmailManagerInboxViewSet, SyncEmailsView

router = DefaultRouter()
router.register(r'emails', EmailManagerViewSet, basename='email-manager')
router.register(r'inbox', EmailManagerInboxViewSet, basename='email-manager-inbox')

urlpatterns = router.urls + [
    path('sync-emails/', SyncEmailsView.as_view(), name='sync-emails'),
    path('emails/send_email/', EmailManagerViewSet.as_view({'post': 'send_email'}), name='send-email'),
]
