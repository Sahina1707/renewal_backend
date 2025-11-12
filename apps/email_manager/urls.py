from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import EmailManagerViewSet, EmailManagerInboxViewSet, SyncEmailsView

router = DefaultRouter()
router.register(r'emails', EmailManagerViewSet, basename='email-manager')
router.register(r'inbox', EmailManagerInboxViewSet, basename='email-manager-inbox')

urlpatterns = router.urls + [
    path('', include(router.urls)),
    # path('emails/send_email/', EmailManagerViewSet.as_view({'post': 'send_email'}), name='send-email'),
]
