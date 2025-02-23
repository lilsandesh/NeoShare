from django.db import models
from django.utils.timezone import now
from datetime import timedelta
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

def default_expiry():
    return now() + timedelta(days=7)  # Set expiry 7 days from now

class OTP(models.Model):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)  # Correct reference

    def is_expired(self):
        return self.expires_at < now()  # Proper timezone handling
class Room(models.Model):
    code = models.CharField(max_length=6, unique=True)
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name="admin_rooms")
    users = models.ManyToManyField(User, related_name="joined_rooms")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Room {self.code} (Admin: {self.admin.username})"
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    google_name = models.CharField(max_length=255, null=True, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    room_code = models.CharField(max_length=20, null=True, blank=True)
    def __str__(self):
        return f"{self.user.username}'s profile"
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
class FileTransfer(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_files')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_files')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_malicious = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Transfer from {self.sender} to {self.receiver}"
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    class Meta:
        ordering = ['-timestamp']
    def __str__(self):
        return f"Notification for {self.user}"
# models.py
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    google_name = models.CharField(max_length=255, null=True, blank=True)
    # ... other fields ...
    def get_display_name(self):
        if self.google_name:
            return self.google_name
        return self.user.username
    