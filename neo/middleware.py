from django.http import HttpResponseRedirect  # Import HttpResponseRedirect for redirecting requests
from django.urls import reverse  # Import reverse to generate URL names dynamically
from .models import UserProfile  # Import UserProfile model for user-specific data
import logging  # Import logging module for debugging and logging
from django.utils import timezone  # Import timezone utility for handling timestamps

logger = logging.getLogger(__name__)  # Create a logger instance for this module

class LoginRequiredMiddleware:  # Define a middleware class for authentication checks
    def __init__(self, get_response):  # Constructor method for the middleware
        self.get_response = get_response  # Store the get_response callable to pass the request down the chain

    def __call__(self, request):  # Method called for each HTTP request
        protected_paths = ['/dashboard/', '/room/']  # List of paths requiring authentication
        path = request.path  # Get the current request path

        if any(path.startswith(protected) for protected in protected_paths):  # Check if the path is protected
            # Check if user is authenticated
            if not request.user.is_authenticated:  # If user is not logged in
                return HttpResponseRedirect(reverse('login'))  # Redirect to the login page
            
            # For each tab, ensure a fresh session or force re-authentication
            if 'last_activity' not in request.session or (timezone.now() - timezone.make_aware(timezone.datetime.fromtimestamp(request.session['last_activity']))).total_seconds() > 300:  # Check if session is missing last_activity or older than 5 minutes
                # Regenerate session to ensure per-tab isolation
                request.session.flush()  # Clear the current session data
                request.session['last_activity'] = timezone.now().timestamp()  # Set new last activity timestamp
                return HttpResponseRedirect(reverse('login'))  # Redirect to login page to force re-authentication
            
            # Update last activity for this session
            request.session['last_activity'] = timezone.now().timestamp()  # Update the last activity timestamp

            # Additional check for room_code if accessing /dashboard/
            if path.startswith('/dashboard/'):  # If the path is for the dashboard
                try:  # Begin try block to fetch user profile
                    user_profile = UserProfile.objects.get(user=request.user)  # Get the UserProfile for the current user
                    if not user_profile.room_code:  # Check if the user has a room code
                        return HttpResponseRedirect(reverse('room'))  # Redirect to room selection if no room code
                except UserProfile.DoesNotExist:  # If no UserProfile exists for the user
                    request.session.flush()  # Clear the session
                    return HttpResponseRedirect(reverse('login'))  # Redirect to login page

        response = self.get_response(request)  # Pass the request to the next middleware or view
        return response  # Return the response to the client