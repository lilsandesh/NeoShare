# neo/consumers.py
import json  # Import JSON module for encoding/decoding messages
import logging  # Import logging module for debugging and logging
import time  # Import time module for rate limiting
from collections import defaultdict  # Import defaultdict from collections module
logger = logging.getLogger(__name__)  # Create a logger instance for this module
from channels.generic.websocket import AsyncWebsocketConsumer  # Import base WebSocket consumer class
from .models import UserProfile, Room, FileTransfer  # Import models for database interaction
from django.utils import timezone  # Import timezone utility for timestamp handling
from channels.db import database_sync_to_async  # Import utility to run sync DB calls asynchronously
from asgiref.sync import sync_to_async  # Import utility to convert sync functions to async

class LiveUserConsumer(AsyncWebsocketConsumer):  # Define consumer for live user tracking
    active_users = set()  # Class-level set to track active usernames

    async def connect(self):  # Method called when a WebSocket connection is established
        if self.scope["user"].is_authenticated:  # Check if the user is authenticated
            self.username = self.scope["user"].username  # Store the username from the scope
            
            # Update user profile
            user_profile = await self.get_or_create_profile()  # Get or create the user’s profile
            user_profile.is_online = True  # Set the user as online
            user_profile.last_seen = timezone.now()  # Update last seen timestamp
            await self.save_profile(user_profile)  # Save the updated profile
            
            LiveUserConsumer.active_users.add(self.username)  # Add username to active users set
            await self.channel_layer.group_add("live_users", self.channel_name)  # Add channel to live_users group
            await self.accept()  # Accept the WebSocket connection
            await self.broadcast_user_list()  # Broadcast updated user list to the group
        else:  # If user is not authenticated
            await self.close()  # Close the connection

    async def disconnect(self, close_code):  # Method called when WebSocket disconnects
        if hasattr(self, 'username'):  # Check if username was set (i.e., connection was established)
            LiveUserConsumer.active_users.discard(self.username)  # Remove username from active users
            
            user_profile = await self.get_or_create_profile()  # Get or create the user’s profile
            user_profile.is_online = False  # Set the user as offline
            user_profile.last_seen = timezone.now()  # Update last seen timestamp
            await self.save_profile(user_profile)  # Save the updated profile
            
            await self.channel_layer.group_discard("live_users", self.channel_name)  # Remove channel from group
            await self.broadcast_user_list()  # Broadcast updated user list

    async def broadcast_user_list(self):  # Method to send the active user list to the group
        await self.channel_layer.group_send(  # Send message to the live_users group
            "live_users",  # Group name
            {
                "type": "update_users",  # Message type for handler
                "users": list(LiveUserConsumer.active_users),  # List of active usernames
            },
        )

    async def update_users(self, event):  # Handler for update_users messages
        await self.send(text_data=json.dumps({  # Send the user list to the client
            "users": event["users"]  # Extract users from the event
        }))

    async def get_or_create_profile(self):  # Method to get or create a UserProfile
        @database_sync_to_async  # Decorator to run sync DB code asynchronously
        def get_profile():  # Inner sync function
            profile, created = UserProfile.objects.get_or_create(  # Get or create profile
                user=self.scope["user"]  # Based on the current user
            )
            return profile  # Return the profile object
        return await get_profile()  # Await and return the result

    async def save_profile(self, profile):  # Method to save a UserProfile
        @database_sync_to_async  # Decorator to run sync DB code asynchronously
        def save():  # Inner sync function
            profile.save()  # Save the profile to the database
        await save()  # Await the save operation

class DashboardConsumer(AsyncWebsocketConsumer):  # Define consumer for dashboard updates
    async def connect(self):  # Method called when a WebSocket connection is established
        try:  # Try to get the room code from the URL
            self.room_code = self.scope["url_route"]["kwargs"]["room_code"]  # Extract room code from URL route
        except KeyError:  # If room_code is missing
            await self.close()  # Close the connection
            return

        if not self.room_code:  # If room code is empty
            await self.close()  # Close the connection
            return

        self.room_group_name = f"dashboard_{self.room_code}"  # Set group name based on room code

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)  # Add channel to group
        await self.accept()  # Accept the WebSocket connection

        await self.send_users_update()  # Send initial user update

    async def disconnect(self, close_code):  # Method called when WebSocket disconnects
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)  # Remove channel from group

    async def receive(self, text_data):  # Method to handle incoming messages
        text_data_json = json.loads(text_data)  # Parse JSON message
        message_type = text_data_json.get("type")  # Get message type

        if message_type == "user_notification":  # If message is a notification
            await self.channel_layer.group_send(  # Send notification to the group
                self.room_group_name,
                {
                    "type": "user_notification",  # Message type for handler
                    "message": text_data_json["message"],  # Notification message
                    "user_id": text_data_json["user_id"],  # User ID
                }
            )

    async def user_notification(self, event):  # Handler for user_notification messages
        message = event["message"]  # Extract message
        user_id = event["user_id"]  # Extract user ID
        await self.send(text_data=json.dumps({"type": "notification", "message": message, "user_id": user_id}))  # Send to client

    async def send_users_update(self):  # Method to send updated user list
        room = await sync_to_async(Room.objects.get)(code=self.room_code)  # Get the Room object
        room_users = await sync_to_async(list)(  # Get list of online users in the room
            UserProfile.objects.filter(room_code=self.room_code, is_online=True).select_related('user')
        )

        admin_user = await sync_to_async(lambda: room.admin)()  # Get the room’s admin user

        users_data = [  # Create list of user data dictionaries
            {
                'id': profile.user.id,  # User ID
                'username': profile.google_name or profile.user.username,  # Username or Google name
                'is_google_user': bool(profile.google_name),  # Flag for Google user
                'join_time': profile.user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),  # Join timestamp
                'is_current_user': profile.user == self.scope["user"],  # Flag for current user
                'is_super_user': profile.user == admin_user  # Flag for superuser (admin)
            }
            for profile in room_users  # Iterate over room users
        ]

        print(f"Sending users_data to {self.room_group_name}: {users_data}")  # Log the data being sent

        await self.channel_layer.group_send(  # Send user update to the group
            self.room_group_name,
            {
                'type': 'users_update',  # Message type for handler
                'users': users_data  # User data list
            }
        )

    async def users_update(self, event):  # Handler for users_update messages
        users = event["users"]  # Extract users from event
        await self.send(text_data=json.dumps({"type": "users_update", "users": users}))  # Send to client

# neo/consumers.py
class FileTransferConsumer(AsyncWebsocketConsumer):  # Define consumer for file transfer signaling
    rate_limits = defaultdict(list)  # Store timestamps of messages per user
    MAX_MESSAGES_PER_MINUTE = 10  # Maximum messages per minute
    async def connect(self):  # Method called when a WebSocket connection is established
        self.user = self.scope['user']  # Get the user from the scope
        if not self.user.is_authenticated:  # Check if user is authenticated
            await self.close()  # Close the connection if not
            return

        self.user_id = str(self.user.id)  # Store user ID as string
        self.notification_group = f"user_{self.user_id}_notifications"  # Set group name for notifications
        await self.channel_layer.group_add(self.notification_group, self.channel_name)  # Add channel to group
        await self.accept()  # Accept the WebSocket connection
        logger.info(f"[FileTransferConsumer] User {self.user_id} connected to {self.notification_group}")  # Log connection

    async def disconnect(self, close_code):  # Method called when WebSocket disconnects
        await self.channel_layer.group_discard(self.notification_group, self.channel_name)  # Remove channel from group
        logger.info(f"[FileTransferConsumer] User {self.user_id} disconnected from {self.notification_group}")  # Log disconnection

    async def receive(self, text_data):  # Method to handle incoming messages

        # Rate limiting logic
        current_time = time.time()
        user_messages = self.rate_limits[self.user_id]
        user_messages.append(current_time)
        # Keep only messages from the last 60 seconds
        self.rate_limits[self.user_id] = [t for t in user_messages if current_time - t < 60]
        
        if len(self.rate_limits[self.user_id]) > self.MAX_MESSAGES_PER_MINUTE:
            logger.warning(f"User {self.user_id} exceeded rate limit")
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Rate limit exceeded. Please try again later."
            }))
            return
        data = json.loads(text_data)  # Parse JSON message
        action = data.get('action')  # Get action type
        sender_id = data.get('sender_id', self.user_id)  # Get sender ID, default to current user

        if action == 'file_transfer_request':  # If it’s a file transfer request
            receiver_id = data.get('receiver_id')  # Get receiver ID
            file_name = data.get('file_name')  # Get file name
            file_size = data.get('file_size')  # Get file size
            if not receiver_id or not sender_id:  # Check for required fields
                logger.error(f"Missing receiver_id or sender_id in file_transfer_request: {data}")  # Log error
                return
            logger.info(f"[FileTransferConsumer] Sending file_transfer_request from {sender_id} to {receiver_id}")  # Log request
            await self.channel_layer.group_send(  # Send request to receiver’s group
                f"user_{receiver_id}_notifications",
                {
                    'type': 'webrtc_message',  # Message type for handler
                    'message': {
                        'action': 'file_transfer_request',  # Action type
                        'sender_id': sender_id,  # Sender ID
                        'receiver_id': receiver_id,  # Receiver ID
                        'file_name': file_name,  # File name
                        'file_size': file_size  # File size
                    }
                }
            )

        elif action == 'file_transfer_response':  # If it’s a response to a file transfer request
            receiver_id = data.get('receiver_id')  # Get original sender (now receiver of response)
            accepted = data.get('accepted')  # Get acceptance status
            if not sender_id or not receiver_id:  # Check for required fields
                logger.error(f"Missing sender_id or receiver_id in file_transfer_response: {data}")  # Log error
                return
            logger.info(f"[FileTransferConsumer] Sending file_transfer_response from {sender_id} to {receiver_id}")  # Log response
            await self.channel_layer.group_send(  # Send response to original sender’s group
                f"user_{receiver_id}_notifications",
                {
                    'type': 'webrtc_message',  # Message type for handler
                    'message': {
                        'action': 'file_transfer_response',  # Action type
                        'sender_id': sender_id,  # Responder’s ID
                        'receiver_id': receiver_id,  # Original sender’s ID
                        'accepted': accepted  # Acceptance status
                    }
                }
            )

        elif action in ['webrtc_offer', 'webrtc_ice_candidate']:  # If it’s a WebRTC offer or ICE candidate
            target_id = data.get('receiver_id') if action == 'webrtc_offer' else data.get('target_id')  # Get target ID
            if not target_id:  # Check for required field
                logger.error(f"No target_id in {action} message: {data}")  # Log error
                return
            message = {  # Build message dictionary
                'action': action,  # Action type
                'sender_id': sender_id,  # Sender ID
                'receiver_id': target_id if action == 'webrtc_offer' else None,  # Receiver ID for offer
                'target_id': target_id if action == 'webrtc_ice_candidate' else None,  # Target ID for candidate
            }
            if action == 'webrtc_offer':  # If it’s an offer
                message['offer'] = data.get('offer')  # Add offer data
                logger.info(f"[FileTransferConsumer] Sent WebRTC offer to {target_id} from {sender_id}")  # Log offer
            else:  # If it’s an ICE candidate
                message['candidate'] = data.get('candidate')  # Add candidate data
                logger.info(f"[FileTransferConsumer] Sent WebRTC ICE candidate to {target_id} from {sender_id}")  # Log candidate
            await self.channel_layer.group_send(  # Send message to target’s group
                f"user_{target_id}_notifications",
                {
                    'type': 'webrtc_message',  # Message type for handler
                    'message': message  # Message content
                }
            )

    async def webrtc_message(self, event):  # Handler for webrtc_message events
        message = event['message']  # Extract message from event
        logger.info(f"[FileTransferConsumer] Forwarding message to user {self.user_id}: {message}")  # Log forwarding
        await self.send(text_data=json.dumps({  # Send message to client
            'type': 'webrtc_message',  # Message type
            'message': message  # Message content
        }))