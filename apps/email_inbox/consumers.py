import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

class InboxConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.user = self.scope.get("user")
        
        if not self.user or not self.user.is_authenticated:
            query_string = self.scope.get('query_string', b'').decode()
            params = parse_qs(query_string)
            token = params.get('token', [None])[0]
            
            if token:
                self.user = await self.get_user_from_token(token)

        if not self.user or not self.user.is_authenticated:
            print("WebSocket Auth Failed: No valid user found.")
            await self.close()
            return

        self.inbox_group = "inbox_updates"
        self.email_id = self.scope['url_route']['kwargs'].get('email_id') 
        
        await self.channel_layer.group_add(
            self.inbox_group,
            self.channel_name
        )

        if self.email_id:
            self.presence_group = f"email_{self.email_id}_viewers"
            await self.channel_layer.group_add(
                self.presence_group,
                self.channel_name
            )
            await self.update_presence(join=True)

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'inbox_group'):
            await self.channel_layer.group_discard(
                self.inbox_group,
                self.channel_name
            )

        if hasattr(self, 'presence_group'):
            await self.update_presence(join=False)
            await self.channel_layer.group_discard(
                self.presence_group,
                self.channel_name
            )

    async def update_presence(self, join=True):
        """
        Updates the count of agents viewing this email.
        """
        if not self.user or not self.user.is_authenticated:
            return

        cache_key = f"presence_email_{self.email_id}"
        current_viewers = cache.get(cache_key, set())

        if join:
            current_viewers.add(self.user.id)
        else:
            current_viewers.discard(self.user.id)
        
        cache.set(cache_key, current_viewers, timeout=3600)

        # Broadcast the new count
        await self.channel_layer.group_send(
            self.presence_group,
            {
                "type": "presence_update",
                "viewer_count": len(current_viewers),
                "viewers": list(current_viewers)
            }
        )

    async def inbox_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def presence_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_user_from_token(self, token):
        """
        Manually decodes the JWT token to find the user.
        """
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            User = get_user_model()
            return User.objects.get(id=user_id)
        except Exception as e:
            print(f"JWT Auth Error: {str(e)}")
            return AnonymousUser()