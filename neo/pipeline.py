# pipeline.py

from django.contrib.auth.models import User  # Import Django's built-in User model
from .models import UserProfile  # Import UserProfile model from the current app
import logging  # Import logging module for debugging and logging
from django.utils import timezone  # Import timezone utility for timestamp handling

logger = logging.getLogger(__name__)  # Create a logger instance for this module

def get_or_create_user_profile(backend, user, response, *args, **kwargs):  # Define pipeline function for social auth
    """Create or update user profile after social auth login."""
    # Import models inside the function
    from django.contrib.auth.models import User  # Re-import User model (redundant, already imported above)
    from neo.models import UserProfile  # Import UserProfile from neo app (likely intended instead of .models)
    try:  # Begin try block to handle profile creation/update
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=user)  # Get existing profile or create new one
        
        # Update profile with social auth data
        if backend.name == 'google-oauth2':  # Check if authentication is via Google OAuth2
            profile.google_name = response.get('name')  # Set Google name from response
            profile.is_google_user = True  # Flag as Google user (Note: is_google_user field doesn’t exist in UserProfile model)
            
        profile.save()  # Save the updated or new profile
        logger.info(f"User profile {'created' if created else 'updated'} for {user.username}")  # Log success
        
    except Exception as e:  # Catch any errors during profile handling
        logger.error(f"Error in pipeline for user {user.username}: {e}")  # Log error

def update_user_profile(backend, user, response, *args, **kwargs):  # Define pipeline function to update profile
    """
    Update or create the UserProfile for the authenticated Google user.
    """
    try:  # Begin try block to handle profile update
        # Use user.profile instead of user.userprofile
        profile = user.profile  # Access UserProfile via related_name 'profile' from User model
        profile.google_name = response.get('name')  # Update Google name from response
        profile.is_online = True  # Set user as online
        profile.save()  # Save the updated profile
    except UserProfile.DoesNotExist:  # If profile doesn’t exist
        # Create a new UserProfile if it doesn't exist
        UserProfile.objects.create(  # Create new UserProfile instance
            user=user,  # Link to the authenticated user
            google_name=response.get('name'),  # Set Google name
            is_online=True  # Set initial online status
        )
    return {'user': user}  # Return dict with user object for pipeline chain

# Custom pipeline function in `pipeline.py` or `views.py`
def save_google_profile(backend, user, response, *args, **kwargs):  # Define pipeline function to save Google profile
    """
    Save Google OAuth profile data to the UserProfile model.
    """
    try:  # Begin try block to handle profile save
        profile, created = UserProfile.objects.get_or_create(user=user)  # Get existing profile or create new one
        if backend.name == 'google-oauth2':  # Check if authentication is via Google OAuth2
            profile.google_name = response.get('name', user.username)  # Set Google name, fallback to username
            profile.is_online = True  # Set user as online
            profile.last_seen = timezone.now()  # Update last seen timestamp
            profile.save()  # Save the updated or new profile
    except Exception as e:  # Catch any errors during profile save
        print(f"Error saving Google profile: {str(e)}")  # Print error to console (not logged via logger)