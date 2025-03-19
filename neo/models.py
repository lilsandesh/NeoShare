from django.db import models  # Import Django's models module for defining database models
from django.contrib.auth.models import User  # Import Django's built-in User model
from django.db.models.signals import post_save  # Import post_save signal for automatic actions after saving
from django.dispatch import receiver  # Import receiver decorator for signal handling
from django.utils.timezone import now  # Import now function for current timestamp with timezone
from datetime import timedelta  # Import timedelta for calculating time differences

def default_expiry():  # Define a function to set the default OTP expiry time
    return now() + timedelta(days=7)  # Return current time plus 7 days

class OTP(models.Model):  # Define OTP model for one-time password management
    email = models.EmailField(unique=True)  # Email field, must be unique for each OTP
    otp = models.CharField(max_length=6)  # OTP code field, limited to 6 characters
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of creation, set automatically
    expires_at = models.DateTimeField(default=default_expiry)  # Expiry timestamp, defaults to 7 days from now

    def is_expired(self):  # Method to check if the OTP has expired
        return self.expires_at < now()  # Return True if expiry time is past current time

class UserProfile(models.Model):  # Define UserProfile model to extend User with additional data
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')  # One-to-one link to User, delete profile if user is deleted
    room_code = models.CharField(max_length=10, null=True, blank=True, default=None)  # Room code field, optional
    google_name = models.CharField(max_length=255, null=True, blank=True)  # Google name field, optional for Google auth users
    is_online = models.BooleanField(default=False)  # Flag to indicate if user is online
    last_seen = models.DateTimeField(null=True, blank=True)  # Timestamp of last activity, optional

    def __str__(self):  # String representation of the UserProfile
        return self.google_name or self.user.username  # Return Google name if exists, otherwise username

@receiver(post_save, sender=User)  # Signal receiver for post-save on User model
def create_user_profile(sender, instance, created, **kwargs):  # Function to create UserProfile when User is created
    if created:  # Check if the User instance was just created
        UserProfile.objects.create(user=instance)  # Create a new UserProfile linked to the User

@receiver(post_save, sender=User)  # Signal receiver for post-save on User model
def save_user_profile(sender, instance, **kwargs):  # Function to save UserProfile when User is updated
    try:  # Begin try block to access profile
        instance.profile.save()  # Save the associated UserProfile
    except UserProfile.DoesNotExist:  # If no UserProfile exists
        UserProfile.objects.create(user=instance)  # Create a new UserProfile

class Room(models.Model):  # Define Room model for managing chat/file-sharing rooms
    code = models.CharField(max_length=10, unique=True)  # Unique room code, max 10 characters
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_rooms')  # Foreign key to User as admin, delete room if admin is deleted
    users = models.ManyToManyField(User, related_name='joined_rooms')  # Many-to-many relation for users in the room
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of room creation, set automatically
    status = models.CharField(max_length=10, default='active')  # Room status, defaults to 'active'

    def __str__(self):  # String representation of the Room
        return f"Room {self.code} (Admin: {self.admin.username if self.admin else 'None'})"  # Return room code and admin username

class FileTransfer(models.Model):  # Define FileTransfer model for tracking file exchanges
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_files')  # Foreign key to User who sent the file
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_files')  # Foreign key to User who received the file
    timestamp = models.DateTimeField(auto_now_add=True)  # Timestamp of transfer, set automatically
    is_malicious = models.BooleanField(default=False)  # Flag to mark if file is malicious
    
    def __str__(self):  # String representation of the FileTransfer
        return f"Transfer from {self.sender} to {self.receiver}"  # Return sender and receiver usernames

class Notification(models.Model):  # Define Notification model for user alerts
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Foreign key to User receiving the notification
    message = models.TextField()  # Text content of the notification
    timestamp = models.DateTimeField(auto_now_add=True)  # Timestamp of notification creation, set automatically
    is_read = models.BooleanField(default=False)  # Flag to indicate if notification has been read

    class Meta:  # Meta class for additional model options
        ordering = ['-timestamp']  # Order notifications by timestamp, newest first

    def __str__(self):  # String representation of the Notification
        return f"Notification for {self.user}"  # Return user associated with the notification