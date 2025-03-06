from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import UserProfile
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        protected_paths = ['/dashboard/', '/room/']
        path = request.path

        if any(path.startswith(protected) for protected in protected_paths):
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return HttpResponseRedirect(reverse('login'))
            
            # For each tab, ensure a fresh session or force re-authentication
            if 'last_activity' not in request.session or (timezone.now() - timezone.make_aware(timezone.datetime.fromtimestamp(request.session['last_activity']))).total_seconds() > 300:  # 5 minutes timeout
                # Regenerate session to ensure per-tab isolation
                request.session.flush()
                request.session['last_activity'] = timezone.now().timestamp()
                return HttpResponseRedirect(reverse('login'))
            
            # Update last activity for this session
            request.session['last_activity'] = timezone.now().timestamp()

            # Additional check for room_code if accessing /dashboard/
            if path.startswith('/dashboard/'):
                try:
                    user_profile = UserProfile.objects.get(user=request.user)
                    if not user_profile.room_code:
                        return HttpResponseRedirect(reverse('room'))
                except UserProfile.DoesNotExist:
                    request.session.flush()
                    return HttpResponseRedirect(reverse('login'))

        response = self.get_response(request)
        return response