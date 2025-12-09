from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # General Inbox
    re_path(r'ws/inbox/$', consumers.InboxConsumer.as_asgi()),
    re_path(r'ws/inbox/(?P<email_id>[\w\-\.@]+)/$', consumers.InboxConsumer.as_asgi()),
]