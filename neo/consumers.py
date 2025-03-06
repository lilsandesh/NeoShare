# neo/consumers.py
import json
import logging

logger = logging.getLogger(__name__)
from channels.generic.websocket import AsyncWebsocketConsumer
import logging
from .models import UserProfile, Room, FileTransfer
from neo.dht_module import DHTManager  # Adjusted import statement
from django.utils import timezone
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
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


# neo/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import UserProfile, Room
import logging

logger = logging.getLogger(__name__)

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get room_code from URL kwargs
        try:
            self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        except KeyError:
            await self.close()
            return  # Close the connection if room_code is not provided

        if not self.room_code:
            await self.close()
            return

        self.room_group_name = f"dashboard_{self.room_code}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Send initial users data
        await self.send_users_update()

    async def disconnect(self, close_code):
        # Leave room group
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
        # Fetch room and related data using sync_to_async
        room = await sync_to_async(Room.objects.get)(code=self.room_code)
        room_users = await sync_to_async(list)(
            UserProfile.objects.filter(room_code=self.room_code, is_online=True).select_related('user')
        )

        # Fetch admin user synchronously
        admin_user = await sync_to_async(lambda: room.admin)()

        # Prepare users data
        users_data = [
            {
                'id': profile.user.id,
                'username': profile.google_name or profile.user.username,
                'is_google_user': bool(profile.google_name),
                'join_time': profile.user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                'is_current_user': profile.user == self.scope["user"],
                'is_super_user': profile.user == admin_user  # Compare with admin_user
            }
            for profile in room_users
        ]

        print(f"Sending users_data to {self.room_group_name}: {users_data}")

        # Send the users update to the group
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
# neo/consumers.py
class FileTransferConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.user_id = str(self.user.id) if self.user.is_authenticated else None
        self.notification_group = f"user_{self.user_id}_notifications"
        await self.channel_layer.group_add(self.notification_group, self.channel_name)
        await self.accept()
        print(f"[FileTransferConsumer] User {self.user_id} connected to {self.notification_group}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.notification_group, self.channel_name)

    async def mark_user_offline(self):
        user_profile = await sync_to_async(UserProfile.objects.get)(user=self.user)
        user_profile.is_online = False
        user_profile.last_seen = timezone.now()
        await sync_to_async(user_profile.save)()

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'file_transfer_request':
            receiver_id = data.get('receiver_id')
            sender_id = data.get('sender_id')
            file_name = data.get('file_name')
            file_size = data.get('file_size')
            print(f"Received action file_transfer_request for user {receiver_id}: {data}")
            await self.channel_layer.group_send(
                f"user_{receiver_id}_notifications",
                {
                    'type': 'webrtc_message',
                    'message': {
                        'action': 'file_transfer_request',
                        'sender_id': sender_id,
                        'file_name': file_name,
                        'file_size': file_size
                    }
                }
            )

        elif action == 'file_transfer_response':
            receiver_id = data.get('receiver_id')
            sender_id = data.get('sender_id')
            accepted = data.get('accepted')
            if not sender_id:
                print(f"No sender_id in file_transfer_response message: {data}")
                return
            print(f"Received action file_transfer_response for user {self.user_id}: {data}")
            await self.channel_layer.group_send(
                f"user_{receiver_id}_notifications",
                {
                    'type': 'webrtc_message',
                    'message': {
                        'action': 'file_transfer_response',
                        'sender_id': sender_id,
                        'accepted': accepted
                    }
                }
            )
            print(f"File transfer response sent to user {receiver_id}: accepted={accepted}")

        elif action in ['webrtc_offer', 'webrtc_ice_candidate']:
            target_id = data.get('receiver_id') if action == 'webrtc_offer' else data.get('target_id')
            if not target_id:
                print(f"No {'receiver_id' if action == 'webrtc_offer' else 'target_id'} in {action} message: {data}")
                return
            message = {
                'action': action,
                'sender_id': self.user_id,
            }
            if action == 'webrtc_offer':
                message['offer'] = data.get('offer')
                print(f"Sent WebRTC offer to user {target_id} from user {self.user_id}: {message['offer']}")
            else:
                message['candidate'] = data.get('candidate')
                print(f"Sent WebRTC ICE candidate to user {target_id} from user {self.user_id}: {message['candidate']}")
            await self.channel_layer.group_send(
                f"user_{target_id}_notifications",
                {
                    'type': 'webrtc_message',
                    'message': message
                }
            )

    async def file_transfer_request(self, event):
        await self.send(text_data=json.dumps({
            'action': 'file_transfer_request',
            'sender_id': event['sender_id'],
            'file_name': event['file_name'],
            'file_size': event['file_size']
        }))

    # neo/consumers.py
    async def webrtc_offer(self, event):
        # Use 'receiver_id' from the message or fallback to group context if needed
        receiver_id = event.get('message', {}).get('receiver_id') or event.get('receiver_id')
        if not receiver_id:
            logger.error(f"No receiver_id in webrtc_offer message: {event}")
            return
        
        offer = event.get('message', {}).get('offer', {})
        await self.channel_layer.group_send(
            f"user_{receiver_id}_notifications",
            {
                'type': 'webrtc_offer',
                'message': {
                    'sender_id': self.user_id,
                    'offer': offer
                }
            }
        )
        logger.info(f"Sent WebRTC offer to user {receiver_id} from user {self.user_id}")
        
    async def webrtc_ice_candidate(self, event):
        # Use 'target_id' from the message or fallback to group context if needed
        target_id = event.get('message', {}).get('target_id') or event.get('target_id')
        if not target_id:
            logger.error(f"No target_id in webrtc_ice_candidate message: {event}")
            return
        
        candidate = event.get('message', {}).get('candidate', {})
        await self.channel_layer.group_send(
            f"user_{target_id}_notifications",
            {
                'type': 'webrtc_ice_candidate',
                'message': {
                    'sender_id': self.user_id,
                    'candidate': candidate
                }
            }
        )
        logger.info(f"Sent WebRTC ICE candidate to user {target_id} from user {self.user_id}")

    async def webrtc_answer(self, event):
        receiver_id = event.get('receiver_id')
        if not receiver_id:
            logger.error(f"No receiver_id in webrtc_answer message: {event}")
            return
        
        answer = event.get('answer', {})
        await self.channel_layer.group_send(
            f"user_{receiver_id}_notifications",
            {
                'type': 'webrtc_answer',
                'message': {
                    'sender_id': self.user_id,
                    'answer': answer
                }
            }
        )
        logger.info(f"Sent WebRTC answer to user {receiver_id} from user {self.user_id}")

    async def handle_webrtc_signal(self, data, signal_type):
        target_id = data.get('target_id') if signal_type == 'webrtc_ice_candidate' else data.get('sender_id')
        if not target_id:
            logger.error(f"No target_id or sender_id in {signal_type} message: {data}")
            return

        message_key = 'candidate' if signal_type == 'webrtc_ice_candidate' else signal_type.split('_')[1]
        await self.channel_layer.group_send(
            f"user_{target_id}_notifications",
            {
                'type': signal_type,
                'message': {
                    'sender_id': self.user_id,
                    message_key: data.get(message_key, data.get(signal_type.split('_')[1], None))
                }
            }
        )
        logger.info(f"Sent {signal_type} to user {target_id} from user {self.user_id}")
    

    async def webrtc_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'webrtc_message',
            'message': message
        }))

    # neo/consumers.py
    async def file_transfer_response(self, event):
        # Use 'sender_id' from the message or fallback to group context if needed
        sender_id = event.get('message', {}).get('sender_id') or event.get('sender_id')
        if not sender_id:
            logger.error(f"No sender_id in file_transfer_response message: {event}")
            return
        
        accepted = event.get('message', {}).get('accepted', False) or event.get('accepted', False)
        await self.channel_layer.group_send(
            f"user_{sender_id}_notifications",
            {
                'type': 'file_transfer_response',
                'receiver_id': self.user_id,
                'accepted': accepted
            }
        )
        logger.info(f"File transfer response sent to user {sender_id}: accepted={accepted}")