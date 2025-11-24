from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # General Inbox connection (New Email Alerts)
    re_path(r'ws/inbox/$', consumers.InboxConsumer.as_asgi()),
    
    # Viewing a specific email (Presence tracking)
    re_path(r'ws/inbox/(?P<email_id>[\w-]+)/$', consumers.InboxConsumer.as_asgi()),
]