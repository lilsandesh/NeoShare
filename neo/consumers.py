# neo/consumers.py
import json
import logging

logger = logging.getLogger(__name__)
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import UserProfile, Room, FileTransfer
from django.utils import timezone
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

class LiveUserConsumer(AsyncWebsocketConsumer):
    active_users = set()

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
    async def connect(self):
        try:
            self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        except KeyError:
            await self.close()
            return

        if not self.room_code:
            await self.close()
            return

        self.room_group_name = f"dashboard_{self.room_code}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send_users_update()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get("type")

        if message_type == "user_notification":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_notification",
                    "message": text_data_json["message"],
                    "user_id": text_data_json["user_id"],
                }
            )

    async def user_notification(self, event):
        message = event["message"]
        user_id = event["user_id"]
        await self.send(text_data=json.dumps({"type": "notification", "message": message, "user_id": user_id}))

    async def send_users_update(self):
        room = await sync_to_async(Room.objects.get)(code=self.room_code)
        room_users = await sync_to_async(list)(
            UserProfile.objects.filter(room_code=self.room_code, is_online=True).select_related('user')
        )

        admin_user = await sync_to_async(lambda: room.admin)()

        users_data = [
            {
                'id': profile.user.id,
                'username': profile.google_name or profile.user.username,
                'is_google_user': bool(profile.google_name),
                'join_time': profile.user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                'is_current_user': profile.user == self.scope["user"],
                'is_super_user': profile.user == admin_user
            }
            for profile in room_users
        ]

        print(f"Sending users_data to {self.room_group_name}: {users_data}")

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'users_update',
                'users': users_data
            }
        )

    async def users_update(self, event):
        users = event["users"]
        await self.send(text_data=json.dumps({"type": "users_update", "users": users}))

# neo/consumers.py
class FileTransferConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_id = str(self.user.id)
        self.notification_group = f"user_{self.user_id}_notifications"
        await self.channel_layer.group_add(self.notification_group, self.channel_name)
        await self.accept()
        logger.info(f"[FileTransferConsumer] User {self.user_id} connected to {self.notification_group}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.notification_group, self.channel_name)
        logger.info(f"[FileTransferConsumer] User {self.user_id} disconnected from {self.notification_group}")

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        sender_id = data.get('sender_id', self.user_id)  # Default to current user if not provided

        if action == 'file_transfer_request':
            receiver_id = data.get('receiver_id')
            file_name = data.get('file_name')
            file_size = data.get('file_size')
            if not receiver_id or not sender_id:
                logger.error(f"Missing receiver_id or sender_id in file_transfer_request: {data}")
                return
            logger.info(f"[FileTransferConsumer] Sending file_transfer_request from {sender_id} to {receiver_id}")
            await self.channel_layer.group_send(
                f"user_{receiver_id}_notifications",
                {
                    'type': 'webrtc_message',
                    'message': {
                        'action': 'file_transfer_request',
                        'sender_id': sender_id,
                        'receiver_id': receiver_id,
                        'file_name': file_name,
                        'file_size': file_size
                    }
                }
            )

        elif action == 'file_transfer_response':
            receiver_id = data.get('receiver_id')  # Original sender
            accepted = data.get('accepted')
            if not sender_id or not receiver_id:
                logger.error(f"Missing sender_id or receiver_id in file_transfer_response: {data}")
                return
            logger.info(f"[FileTransferConsumer] Sending file_transfer_response from {sender_id} to {receiver_id}")
            await self.channel_layer.group_send(
                f"user_{receiver_id}_notifications",
                {
                    'type': 'webrtc_message',
                    'message': {
                        'action': 'file_transfer_response',
                        'sender_id': sender_id,
                        'receiver_id': receiver_id,
                        'accepted': accepted
                    }
                }
            )

        elif action in ['webrtc_offer', 'webrtc_ice_candidate']:
            target_id = data.get('receiver_id') if action == 'webrtc_offer' else data.get('target_id')
            if not target_id:
                logger.error(f"No target_id in {action} message: {data}")
                return
            message = {
                'action': action,
                'sender_id': sender_id,
                'receiver_id': target_id if action == 'webrtc_offer' else None,
                'target_id': target_id if action == 'webrtc_ice_candidate' else None,
            }
            if action == 'webrtc_offer':
                message['offer'] = data.get('offer')
                logger.info(f"[FileTransferConsumer] Sent WebRTC offer to {target_id} from {sender_id}")
            else:
                message['candidate'] = data.get('candidate')
                logger.info(f"[FileTransferConsumer] Sent WebRTC ICE candidate to {target_id} from {sender_id}")
            await self.channel_layer.group_send(
                f"user_{target_id}_notifications",
                {
                    'type': 'webrtc_message',
                    'message': message
                }
            )

    async def webrtc_message(self, event):
        message = event['message']
        logger.info(f"[FileTransferConsumer] Forwarding message to user {self.user_id}: {message}")
        await self.send(text_data=json.dumps({
            'type': 'webrtc_message',
            'message': message
        }))