# pipeline.py

from django.contrib.auth.models import User
from .models import UserProfile
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_or_create_user_profile(backend, user, response, *args, **kwargs):
    """Create or update user profile after social auth login."""
        # Import models inside the function
    from django.contrib.auth.models import User
    from neo.models import UserProfile
    try:
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Update profile with social auth data
        if backend.name == 'google-oauth2':
            profile.google_name = response.get('name')
            profile.is_google_user = True
            
        profile.save()
        logger.info(f"User profile {'created' if created else 'updated'} for {user.username}")
        
    except Exception as e:
        logger.error(f"Error in pipeline for user {user.username}: {e}")

def update_user_profile(backend, user, response, *args, **kwargs):
    """
    Update or create the UserProfile for the authenticated Google user.
    """
    try:
        # Use user.profile instead of user.userprofile
        profile = user.profile
        profile.google_name = response.get('name')  # Update with Google's full name
        profile.is_online = True  # Set user as online
        profile.save()
    except UserProfile.DoesNotExist:
        # Create a new UserProfile if it doesn't exist
        UserProfile.objects.create(
            user=user,
            google_name=response.get('name'),
            is_online=True
        )
    return {'user': user}
# Custom pipeline function in `pipeline.py` or `views.py`
def save_google_profile(backend, user, response, *args, **kwargs):
    """
    Save Google OAuth profile data to the UserProfile model.
    """
    try:
        profile, created = UserProfile.objects.get_or_create(user=user)
        if backend.name == 'google-oauth2':
            profile.google_name = response.get('name', user.username)
            profile.is_online = True  # Set initial online status
            profile.last_seen = timezone.now()
            profile.save()
    except Exception as e:
        print(f"Error saving Google profile: {str(e)}")