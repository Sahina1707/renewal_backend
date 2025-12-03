import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache

class InboxConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return

        # Room group names
        self.inbox_group = "inbox_updates" # For new email alerts
        self.email_id = self.scope['url_route']['kwargs'].get('email_id') # Optional: Viewing specific email
        
        # Join Inbox Updates Group
        await self.channel_layer.group_add(
            self.inbox_group,
            self.channel_name
        )

        # If viewing a specific email, track presence
        if self.email_id:
            self.presence_group = f"email_{self.email_id}_viewers"
            await self.channel_layer.group_add(
                self.presence_group,
                self.channel_name
            )
            await self.update_presence(join=True)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave Inbox Updates Group
        await self.channel_layer.group_discard(
            self.inbox_group,
            self.channel_name
        )

        # If viewing a specific email, leave presence group
        if hasattr(self, 'email_id', None):
            await self.update_presence(join=False)
            await self.channel_layer.group_discard(
                self.presence_group,
                self.channel_name
            )

    async def update_presence(self, join=True):
        """
        Updates the count of agents viewing this email.
        """
        cache_key = f"presence_email_{self.email_id}"
        current_viewers = cache.get(cache_key, set())

        if join:
            current_viewers.add(self.user.id)
        else:
            current_viewers.discard(self.user.id)
        
        # Set expiry for safety (e.g., 1 hour)
        cache.set(cache_key, current_viewers, timeout=3600)

        # Broadcast the new count to everyone in this email room
        await self.channel_layer.group_send(
            self.presence_group,
            {
                "type": "presence_update",
                "viewer_count": len(current_viewers),
                "viewers": list(current_viewers) # Send IDs (Frontend maps to names)
            }
        )

    # --- Handlers for Messages from Group ---

    async def inbox_update(self, event):
        """
        Called when a new email arrives (triggered by Signal).
        """
        await self.send(text_data=json.dumps(event))

    async def presence_update(self, event):
        """
        Called when an agent joins/leaves.
        """
        await self.send(text_data=json.dumps(event))