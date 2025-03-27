from django.shortcuts import render, redirect, HttpResponseRedirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from .models import OTP, Room, Notification, UserProfile, FileTransfer
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
from django.conf import settings
import logging
import random
import asyncio
from neo.dht_module import Server, DHTManager
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.tokens import default_token_generator
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .utils import scan_file_metadefender

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Global DHT Server Instance
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
dht_server = Server()

async def start_dht():
    await dht_server.listen(9000)
    await dht_server.bootstrap([("127.0.0.1", 9000)])

loop.run_until_complete(start_dht())

# Helper Functions
async def get_room(code):
    return await dht_server.get(code)

async def store_room(code, admin_username):
    try:
        dht_manager = await DHTManager.get_instance()
        success = await dht_manager.store_room(code, admin_username)
        if success:
            logger.info(f"Room {code} stored successfully in DHT")
        return success
    except Exception as e:
        logger.error(f"Failed to store room in DHT: {e}")
        return False

async def get_room_from_dht(code):
    try:
        dht_manager = await DHTManager.get_instance()
        return await dht_manager.get_room(code)
    except Exception as e:
        logger.error(f"Failed to retrieve room from DHT: {e}")
        return None

def generate_room_code(length=6):
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=length))

# Authentication Views

def signup(request):
    if request.method == 'POST':
        # Validate reCAPTCHA
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not recaptcha_response:
            return JsonResponse({'error': 'Please complete the reCAPTCHA'}, status=400)

        import requests
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': settings.RECAPTCHA_PRIVATE_KEY,
                'response': recaptcha_response,
                'remoteip': request.META.get('REMOTE_ADDR')
            }
        )
        result = response.json()
        if not result.get('success'):
            return JsonResponse({'error': 'reCAPTCHA verification failed'}, status=400)

        # Proceed with signup logic
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')

        if not all([username, email, password, confirm_password]):
            return JsonResponse({'error': 'All fields are required'}, status=400)

        if password != confirm_password:
            return JsonResponse({'error': 'Passwords do not match'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username already taken'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email already registered'}, status=400)

        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        OTP.objects.filter(email=email).delete()

        try:
            otp_obj = OTP.objects.create(email=email, otp=otp)
            send_mail(
                'Your OTP for Registration',
                f'Your OTP is: {otp}. This OTP will expire in 5 minutes.',
                'littlesandesh123@gmail.com',
                [email]
            )
            request.session['signup_data'] = {
                'username': username,
                'email': email,
                'password': password
            }
            return JsonResponse({'message': 'OTP sent successfully', 'status': 'success'})
        except Exception as e:
            logger.error(f"Error sending OTP: {e}")
            return JsonResponse({'error': 'Failed to send OTP'}, status=500)

    return render(request, 'signup.html')

@require_http_methods(["POST"])
def verify_otp(request):
    try:
        data = json.loads(request.body)
        email = data.get("email")
        entered_otp = data.get("otp")

        if not email or not entered_otp:
            return JsonResponse({"status": "error", "error": "Missing email or OTP"}, status=400)

        otp_record = OTP.objects.get(email=email)
        if otp_record.otp != entered_otp or otp_record.is_expired():
            return JsonResponse({"status": "error", "error": "Invalid or expired OTP"}, status=400)

        signup_data = request.session.get("signup_data")
        if signup_data:
            user = User.objects.create_user(
                username=signup_data["username"],
                email=signup_data["email"],
                password=signup_data["password"]
            )
            user.save()
            del request.session["signup_data"]
            return JsonResponse({"status": "success", "message": "Signup successful", "redirect_url": "/login/"})
        return JsonResponse({"status": "error", "error": "No signup data found"}, status=400)
    except OTP.DoesNotExist:
        return JsonResponse({"status": "error", "error": "OTP not found"}, status=400)
    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        return JsonResponse({"status": "error", "error": str(e)}, status=500)

def login_view(request):
    if request.method == "POST":
        # Validate reCAPTCHA
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not recaptcha_response:
            messages.error(request, "Please complete the reCAPTCHA.")
            return render(request, 'login.html', {
                'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY
            })

        # Verify reCAPTCHA with Google
        import requests
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': settings.RECAPTCHA_PRIVATE_KEY,
                'response': recaptcha_response,
                'remoteip': request.META.get('REMOTE_ADDR')
            }
        )
        result = response.json()
        if not result.get('success'):
            messages.error(request, "reCAPTCHA verification failed. Please try again.")
            return render(request, 'login.html', {
                'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY
            })

        # Proceed with login logic
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        try:
            user = User.objects.get(email=email)
            username = user.username
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                request.session.flush()
                login(request, user)
                request.session['last_activity'] = timezone.now().timestamp()
                return redirect("room")
            else:
                messages.error(request, "Invalid email or password")
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password")
    
    # Handle social auth errors and force logout logic
    error = request.GET.get('error')
    if error:
        messages.error(request, "Authentication failed. Please try again.")
    
    if request.user.is_authenticated:
        user_profile = UserProfile.objects.get(user=request.user)
        user_profile.is_online = False
        user_profile.room_code = None
        user_profile.save()
        logout(request)
        request.session.flush()
        messages.info(request, "Please log in again.")
    
    return render(request, 'login.html', {
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY
    })

# New view to handle Google login with reCAPTCHA verification
def google_login_with_recaptcha(request):
    if request.method == "POST":
        # Validate reCAPTCHA
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not recaptcha_response:
            messages.error(request, "Please complete the reCAPTCHA for Google login.")
            return render(request, 'login.html', {
                'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY
            })

        # Verify reCAPTCHA with Google
        import requests
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': settings.RECAPTCHA_PRIVATE_KEY,
                'response': recaptcha_response,
                'remoteip': request.META.get('REMOTE_ADDR')
            }
        )
        result = response.json()
        if not result.get('success'):
            messages.error(request, "reCAPTCHA verification failed for Google login. Please try again.")
            return render(request, 'login.html', {
                'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY
            })

        # If reCAPTCHA is verified, redirect to Google OAuth2 flow
        return redirect('social:begin', backend='google-oauth2')

    # If not a POST request, redirect back to login page
    return redirect('login')

def handle_auth_error(request):
    messages.error(request, "Authentication failed. Please try again.")
    return redirect('login')

def handle_google_login(backend, user, response, *args, **kwargs):
    user_info = response
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')
    request = kwargs.get('request')

    try:
        social_account = SocialAccount.objects.get(provider='google', uid=google_id)
        user = social_account.user
        logger.info(f"Existing Google account found for {google_id}, linking to user {user.username}")
    except SocialAccount.DoesNotExist:
        try:
            user = User.objects.get(email=email)
            if SocialAccount.objects.filter(user=user, provider='google').exists():
                username = f"{email.split('@')[0]}_{google_id[-4:]}"
                user = User.objects.create_user(username=username, email=email, password=None)
                SocialAccount.objects.create(user=user, provider='google', uid=google_id, extra_data=user_info)
                logger.info(f"New user created for {google_id} with username {username} due to email conflict")
            else:
                SocialAccount.objects.create(user=user, provider='google', uid=google_id, extra_data=user_info)
                logger.info(f"Linked Google ID {google_id} to existing user {user.username}")
        except User.DoesNotExist:
            username = f"{email.split('@')[0]}_{google_id[-4:]}"
            user = User.objects.create_user(username=username, email=email, password=None)
            SocialAccount.objects.create(user=user, provider='google', uid=google_id, extra_data=user_info)
            logger.info(f"New user created for {google_id} with username {username}")

    profile, created = UserProfile.objects.get_or_create(user=user)
    
    if profile.is_online and request.user.is_authenticated and request.user != user:
        logger.warning(f"User {user.username} is already logged in elsewhere. Forcing logout of previous session.")
        previous_session = UserProfile.objects.filter(user=user, is_online=True).exclude(user=request.user).first()
        if previous_session:
            previous_session.is_online = False
            previous_session.room_code = None
            previous_session.save()
    
    profile.google_name = name
    profile.is_online = True
    profile.last_seen = timezone.now()
    profile.room_code = None
    profile.save()
    
    request.session.flush()
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    request.session['last_activity'] = timezone.now().timestamp()
    logger.info(f"User profile updated for {user.username} with Google name {name}")

    if not profile.room_code:
        return redirect('room')
    return redirect('dashboard')

def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = User.objects.filter(email=email).first()

        if user:
            try:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                reset_link = request.build_absolute_uri(
                    reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )

                send_mail(
                    "Reset Your Password",
                    f"Click the link below to reset your password:\n{reset_link}",
                    "littlesandesh123@gmail.com",
                    [email],
                    fail_silently=False,
                )

                messages.success(request, "Password reset link has been sent to your email address.")
                return redirect("login")
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
                return redirect("login")
        else:
            messages.error(request, "No user found with this email address.")
            return redirect("login")

    return render(request, "login.html")

def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            new_password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")

            if new_password and new_password == confirm_password:
                try:
                    user.set_password(new_password)
                    user.save()
                    messages.success(request, "Password has been successfully reset. Please login with your new password.")
                    return redirect("login")
                except Exception as e:
                    messages.error(request, f"An error occurred: {str(e)}")
            else:
                messages.error(request, "Passwords do not match or are empty.")
        return render(request, "password_reset_confirm.html", {
            'uidb64': uidb64,
            'token': token,
            'valid_link': True
        })
    else:
        messages.error(request, "The password reset link is invalid or has expired.")
        return redirect("login")

# Room and Dashboard Views
@login_required(login_url='login')
def room_view(request):
    user_profile = UserProfile.objects.get(user=request.user)
    context = {
        'current_room': user_profile.room_code,
        'username': user_profile.google_name or request.user.username
    }
    return render(request, "room.html", context)

@login_required(login_url='login')
@require_http_methods(["POST"])
def create_room(request):
    admin = request.user
    room_code = generate_room_code()
    
    try:
        room = Room.objects.create(code=room_code, admin=admin)
        room.users.add(admin)
        
        user_profile = UserProfile.objects.get(user=admin)
        user_profile.room_code = room_code
        user_profile.is_online = True
        user_profile.save()
        
        request.session['room_code'] = room_code
        dht_success = async_to_sync(store_room)(room_code, admin.username)
        if not dht_success:
            room.delete()
            return JsonResponse({"status": "error", "message": "Failed to create room in DHT"}, status=500)
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"dashboard_{room_code}",
            {
                'type': 'user_notification',
                'message': f"{user_profile.google_name or admin.username} has created the room",
                'user_id': admin.id
            }
        )
        
        return JsonResponse({"status": "success", "room_code": room_code})
    except Exception as e:
        logger.error(f"Failed to create room: {e}")
        Room.objects.filter(code=room_code).delete()
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@login_required(login_url='login')
@require_http_methods(["POST"])
@csrf_exempt
def join_room(request):
    room_code = request.POST.get("room_code", "").strip()
    if not room_code:
        return JsonResponse({"error": "Room code is required"}, status=400)

    print(f"Received room code: {room_code}")
    try:
        room = Room.objects.get(code=room_code)
        user = request.user
        if user not in room.users.all():
            room.users.add(user)
        
        user_profile, created = UserProfile.objects.get_or_create(user=user)
        user_profile.room_code = room_code
        user_profile.is_online = True
        user_profile.save()

        request.session['room_code'] = room_code
        logger.info(f"User {user.username} joined room {room_code}. Online users: {[u.username for u in room.users.all()]}")

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"dashboard_{room_code}",
            {
                'type': 'user_notification',
                'message': f"{user_profile.google_name or user.username} has joined the room",
                'user_id': user.id
            }
        )
        
        return JsonResponse({"message": "Room joined successfully", "room_code": room_code})
    except Room.DoesNotExist:
        return JsonResponse({"error": "Room not found"}, status=404)
    except Exception as e:
        logger.error(f"Error joining room: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required(login_url='login')
def dashboard_view(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if not user_profile.room_code:
        return redirect('room')
    
    seven_days_ago = timezone.now() - timedelta(days=7)
    room = Room.objects.get(code=user_profile.room_code)
    room_users = UserProfile.objects.filter(room_code=user_profile.room_code, is_online=True).select_related('user')
    
    users_data = [
        {
            'id': profile.user.id,
            'username': profile.google_name or profile.user.username,
            'is_google_user': bool(profile.google_name),
            'join_time': profile.user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            'is_current_user': profile.user == request.user,
            'is_super_user': profile.user == room.admin
        }
        for profile in room_users
    ]

    logger.info(f"Rendering dashboard for {request.user.username} with users_data: {users_data}")
    context = {
        'files_sent': FileTransfer.objects.filter(sender=request.user, timestamp__gte=seven_days_ago).count(),
        'files_received': FileTransfer.objects.filter(receiver=request.user, timestamp__gte=seven_days_ago).count(),
        'notifications': Notification.objects.filter(user=request.user, is_read=False)[:5],
        'room_code': user_profile.room_code,
        'users_data': json.dumps(users_data)
    }
    return render(request, 'dashboard.html', context)

@login_required(login_url='login')
@require_http_methods(["POST"])
def logout_view(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        room_code = user_profile.room_code
        
        if room_code:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"dashboard_{room_code}",
                {
                    'type': 'user_notification',
                    'message': f"{user_profile.google_name or request.user.username} has left the room",
                    'user_id': request.user.id
                }
            )
        
        user_profile.is_online = False
        user_profile.room_code = None
        user_profile.save()
        
        logout(request)
        request.session.flush()
        
        return JsonResponse({"status": "success", "message": "Logged out successfully"})
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return JsonResponse({"status": "error", "message": "Logout failed"}, status=500)

@login_required(login_url='login')
def leave_room(request):
    if request.method == "POST":
        try:
            user_profile = UserProfile.objects.get(user=request.user)
            room_code = user_profile.room_code
            
            if room_code:
                room = Room.objects.get(code=room_code)
                room.users.remove(request.user)
                
                user_profile.room_code = None
                user_profile.is_online = False
                user_profile.save()
                
                request.session.pop('room_code', None)
                
                return JsonResponse({
                    "status": "success",
                    "message": "Left room successfully"
                })
            
            return JsonResponse({
                "status": "error",
                "message": "Not in a room"
            }, status=400)
            
        except Exception as e:
            logger.error(f"Failed to leave room: {e}")
            return JsonResponse({
                "status": "error",
                "message": str(e)
            }, status=500)

@login_required(login_url='login')
def mark_notification_read(request, notification_id):
    Notification.objects.filter(id=notification_id, user=request.user).update(is_read=True)
    return JsonResponse({'status': 'success'})

@login_required(login_url='login')
def room_detail(request, room_code):
    try:
        room = Room.objects.filter(code=room_code).first()
        if not room:
            return redirect('room')
        
        dht_room = async_to_sync(get_room_from_dht)(room_code)
        
        context = {
            'room': room,
            'dht_data': dht_room,
            'is_admin': request.user == room.admin,
            'room_members': room.users.all(),
        }
        
        return render(request, 'room_detail.html', context)
    except Exception as e:
        logger.error(f"Error in room_detail view: {e}")
        return redirect('room')

@login_required(login_url='login')
@require_http_methods(["POST"])
def scan_file(request):
    """Endpoint to scan a file before transfer"""
    try:
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({"error": "No file provided"}, status=400)
            
        # Read file content
        file_content = file.read()
        
        # Scan file
        is_safe, message = scan_file_metadefender(file_content, file.name)
        
        return JsonResponse({
            "safe": is_safe,
            "message": message
        })
    except Exception as e:
        logger.error(f"Error scanning file: {e}")
        return JsonResponse({
            "error": "Failed to scan file",
            "message": str(e)
        }, status=500)