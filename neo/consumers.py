# neo/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
import logging
from .models import UserProfile, Room, FileTransfer
from neo.dht_module import DHTManager  # Adjusted import statement
from django.utils import timezone
from channels.db import database_sync_to_async
import hashlib

class LiveUserConsumer(AsyncWebsocketConsumer):
    active_users = set()

    active_users = {}

    async def connect(self):
        if self.scope["user"].is_authenticated:
            self.username = self.scope["user"].username
            
            # Update user profile
            user_profile = await self.get_or_create_profile()
            user_profile.is_online = True
            user_profile.last_seen = timezone.now()
            await self.save_profile(user_profile)
            
            LiveUserConsumer.active_users.add(self.username)
            await self.channel_layer.group_add("live_users", self.channel_name)
            await self.accept()
            await self.broadcast_user_list()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'username'):
            LiveUserConsumer.active_users.discard(self.username)
            
            user_profile = await self.get_or_create_profile()
            user_profile.is_online = False
            user_profile.last_seen = timezone.now()
            await self.save_profile(user_profile)
            
            await self.channel_layer.group_discard("live_users", self.channel_name)
            await self.broadcast_user_list()

    async def broadcast_user_list(self):
        await self.channel_layer.group_send(
            "live_users",
            {
                "type": "update_users",
                "users": list(LiveUserConsumer.active_users),
            },
        )

    async def update_users(self, event):
        await self.send(text_data=json.dumps({
            "users": event["users"]
        }))

    async def get_or_create_profile(self):
        @database_sync_to_async
        def get_profile():
            profile, created = UserProfile.objects.get_or_create(
                user=self.scope["user"]
            )
            return profile
        return await get_profile()

    async def save_profile(self, profile):
        @database_sync_to_async
        def save():
            profile.save()
        await save()


class DashboardConsumer(AsyncWebsocketConsumer):
    active_users = {}
    async def connect(self):
        self.room_group_name = "dashboard"
        
        if self.scope["user"].is_authenticated:
            user = self.scope["user"]
            profile = await self.get_user_profile(user)
            
            # Generate a unique identifier for the connection
            self.connection_id = f"{user.id}-{self.channel_name}"
            
            # Use Google name if available, otherwise fallback to user's display name
            display_name = None
            if profile and profile.google_name:
                display_name = profile.google_name
            elif user.get_full_name():
                display_name = user.get_full_name()
            else:
                display_name = user.username
                
            # Store user info with unique connection ID
            DashboardConsumer.active_users[self.connection_id] = {
                "username": display_name,
                "join_time": "Just now",
                "id": str(user.id),
                "is_google_user": bool(profile and profile.google_name),
                "connection_id": self.connection_id
            }
        else:
            # Generate unique guest ID
            self.connection_id = f"guest-{self.channel_name[-8:]}"
            self.username = f"Guest-{self.channel_name[-4:]}"
            
            DashboardConsumer.active_users[self.connection_id] = {
                "username": self.username,
                "join_time": "Just now",
                "id": self.connection_id,
                "is_google_user": False,
                "connection_id": self.connection_id
            }

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_users_update()
        
    async def disconnect(self, close_code):
        if hasattr(self, 'connection_id') and self.connection_id in DashboardConsumer.active_users:
            del DashboardConsumer.active_users[self.connection_id]
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            await self.send_users_update()

    async def send_users_update(self):
        # Remove duplicate users by taking the latest connection for each user ID
        unique_users = {}
        for user_data in DashboardConsumer.active_users.values():
            user_id = user_data['id']
            if user_id not in unique_users or user_data['connection_id'] > unique_users[user_id]['connection_id']:
                unique_users[user_id] = user_data

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_list_update',
                'users': list(unique_users.values())
            }
        )

    async def user_list_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'users_update',
            'users': event['users']
        }))

    @database_sync_to_async
    def get_user_profile(self, user):
        try:
            return UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return None
import json
import hashlib
from channels.generic.websocket import AsyncWebsocketConsumer

class FileTransferConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.personal_channel = f"user_{self.user.id}_notifications"
        await self.channel_layer.group_add(
            self.personal_channel,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'personal_channel'):
            await self.channel_layer.group_discard(
                self.personal_channel,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages for signaling"""
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'webrtc_offer':
            await self.handle_webrtc_offer(data)
        elif action == 'webrtc_answer':
            await self.handle_webrtc_answer(data)
        elif action == 'webrtc_ice_candidate':
            await self.handle_webrtc_ice_candidate(data)

    async def handle_webrtc_offer(self, data):
        """Relay WebRTC offer to the receiver"""
        receiver_id = data['receiver_id']
        offer = data['offer']
        
        await self.channel_layer.group_send(
            f"user_{receiver_id}_notifications",
            {
                'type': 'webrtc_offer',
                'message': {
                    'sender_id': self.user.id,
                    'offer': offer
                }
            }
        )

    async def handle_webrtc_answer(self, data):
        """Relay WebRTC answer to the sender"""
        sender_id = data['sender_id']
        answer = data['answer']

        await self.channel_layer.group_send(
            f"user_{sender_id}_notifications",
            {
                'type': 'webrtc_answer',
                'message': {
                    'receiver_id': self.user.id,
                    'answer': answer
                }
            }
        )

    async def handle_webrtc_ice_candidate(self, data):
        """Relay ICE candidates between sender and receiver"""
        target_id = data['target_id']
        candidate = data['candidate']

        await self.channel_layer.group_send(
            f"user_{target_id}_notifications",
            {
                'type': 'webrtc_ice_candidate',
                'message': {
                    'sender_id': self.user.id,
                    'candidate': candidate
                }
            }
        )

    async def webrtc_offer(self, event):
        """Send WebRTC offer to receiver"""
        await self.send(text_data=json.dumps({
            'type': 'webrtc_offer',
            'data': event['message']
        }))

    async def webrtc_answer(self, event):
        """Send WebRTC answer to sender"""
        await self.send(text_data=json.dumps({
            'type': 'webrtc_answer',
            'data': event['message']
        }))

    async def webrtc_ice_candidate(self, event):
        """Send ICE candidate to the target peer"""
        await self.send(text_data=json.dumps({
            'type': 'webrtc_ice_candidate',
            'data': event['message']
        }))
