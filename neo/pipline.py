# pipeline.py

from django.contrib.auth.models import User
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)

def get_or_create_user_profile(backend, user, response, *args, **kwargs):
    """Create or update user profile after social auth login."""
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
    """Update user profile with additional social auth data."""
    if not UserProfile.objects.filter(user=user).exists():
        return
    
    profile = user.userprofile
    
    if backend.name == 'google-oauth2':
        profile.avatar_url = response.get('picture')
        profile.email_verified = response.get('email_verified', False)
        
    profile.save()
    logger.info(f"Updated profile for {user.username} with social auth data")

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'neo.pipeline.get_or_create_user_profile',
    'neo.pipeline.update_user_profile',
)