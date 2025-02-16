from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.utils import timezone 
from datetime import datetime, timedelta
from .models import OTP, Room, Notification, UserProfile, FileTransfer
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
import logging
import random
import asyncio
from neo.dht_module import Server, DHTManager
from django.contrib.auth.tokens import default_token_generator
from asgiref.sync import async_to_sync
from django.contrib.auth.forms import PasswordResetForm
from django.utils.http import urlsafe_base64_encode
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode
from neo.dht_module import DHTManager

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
def SignupPage(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')

        # Basic validation
        if not all([username, email, password, confirm_password]):
            return JsonResponse({'error': 'All fields are required'}, status=400)

        if password != confirm_password:
            return JsonResponse({'error': 'Passwords do not match'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username already taken'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email already registered'}, status=400)

        # Generate OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Delete any existing OTP for this email
        OTP.objects.filter(email=email).delete()

        # Create new OTP
        try:
            otp_obj = OTP.objects.create(
                email=email,
                otp=otp
            )
            
            # Send OTP email
            subject = 'Your OTP for Registration'
            message = f'Your OTP is: {otp}. This OTP will expire in 30 seconds.'
            from_email = 'littlesandesh123@gmail.com'
            recipient_list = [email]
            
            send_mail(subject, message, from_email, recipient_list)

            # Save signup data in session
            request.session['signup_data'] = {
                'username': username,
                'email': email,
                'password': password
            }
            
            return JsonResponse({'message': 'OTP sent successfully', 'status': 'success'})
            
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({'error': 'Failed to send OTP'}, status=500)

    return render(request, 'signup.html')

def VerifyOTPPage(request):
    if request.method == "POST":
        try:
            raw_data = request.body.decode("utf-8")  # Decode request body
            print(f"Raw Request Body: {raw_data}")  # Debugging log

            data = json.loads(raw_data)  # ✅ Parse JSON correctly
            email = data.get("email")
            entered_otp = data.get("otp")

            if not email or not entered_otp:
                return JsonResponse({"status": "error", "error": "Missing email or OTP"}, status=400)

            # Fetch OTP from the database
            try:
                otp_record = OTP.objects.get(email=email)
            except OTP.DoesNotExist:
                return JsonResponse({"status": "error", "error": "OTP not found"}, status=400)

            # Check if OTP matches
            if otp_record.otp == entered_otp:
                # ✅ FIXED: Use timezone-aware now()
                if otp_record.created_at + timedelta(minutes=5) < timezone.now():
                    return JsonResponse({"status": "error", "error": "OTP has expired"}, status=400)

                # Create user after OTP verification
                signup_data = request.session.get("signup_data")
                if signup_data:
                    user = User.objects.create_user(
                        username=signup_data["username"],
                        email=signup_data["email"],
                        password=signup_data["password"]
                    )
                    user.save()
                    del request.session["signup_data"]  # Remove session data after signup

                return JsonResponse({"status": "success", "message": "OTP verified! Redirecting...", "redirect_url": "/login/"})
            else:
                return JsonResponse({"status": "error", "error": "Invalid OTP"}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "error": "Invalid JSON format"}, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)}, status=500)

    return JsonResponse({"status": "error", "error": "Invalid request method"}, status=400)


def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = User.objects.filter(email=email).first()

        if user:
            try:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Build the reset link using request.build_absolute_uri
                reset_link = request.build_absolute_uri(
                    reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )

                # Send the reset email
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

def LoginPage(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        try:
            # Get username from email
            user = User.objects.get(email=email)
            username = user.username
            # Authenticate with username
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                return redirect("room")
            else:
                messages.error(request, "Invalid email or password")
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password")
    
    # Add this to handle social auth errors
    error = request.GET.get('error')
    if error:
        messages.error(request, "Authentication failed. Please try again.")
    
    return render(request, "login.html")

def handle_auth_error(request):
    messages.error(request, "Authentication failed. Please try again.")
    return redirect('login')

def room_view(request):
    return render(request, "room.html")

# Global DHT Server Instance
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
dht_server = Server()

async def start_dht():
    await dht_server.listen(9000)
    await dht_server.bootstrap([("127.0.0.1", 9000)])

loop.run_until_complete(start_dht())

# Retrieve room from DHT
async def get_room(code):
    return await dht_server.get(code)

# Function to generate a unique room code
def generate_room_code(length=6):
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=length))

# Store room in DHT
async def store_room(code, admin_username):
    """Store room information in DHT."""
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
    """Retrieve room information from DHT."""
    try:
        dht_manager = await DHTManager.get_instance()
        return await dht_manager.get_room(code)
    except Exception as e:
        logger.error(f"Failed to retrieve room from DHT: {e}")
        return None

@login_required
@require_http_methods(["POST"])
def create_room(request):
    """Create a new room and store it in both database and DHT."""
    admin = request.user
    room_code = generate_room_code()
    
    try:
        # Create room in database
        room = Room.objects.create(code=room_code, admin=admin)
        room.users.add(admin)
        
        # Get or create user profile
        user_profile, _ = UserProfile.objects.get_or_create(user=admin)
        user_profile.room_code = room_code
        user_profile.save()
        
        # Store in DHT
        dht_success = async_to_sync(store_room)(room_code, admin.username)
        
        if not dht_success:
            logger.error(f"Failed to store room {room_code} in DHT")
            room.delete()
            return JsonResponse({
                "status": "error",
                "message": "Failed to create room in DHT"
            }, status=500)
        
        # Store room code in session
        request.session['room_code'] = room_code
        
        return JsonResponse({
            "status": "success",
            "room_code": room_code,
            "redirect_url": "/dashboard/"
        })
    
    except Exception as e:
        logger.error(f"Failed to create room: {e}")
        # Cleanup any partial creation
        Room.objects.filter(code=room_code).delete()
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

import json

@login_required
@require_http_methods(["POST"])
def join_room(request):
    """Join an existing room."""
    try:
        # Try getting data from JSON if it's sent that way
        data = json.loads(request.body.decode("utf-8")) if request.content_type == "application/json" else request.POST
        room_code = data.get("room_code")

        if not room_code:
            return JsonResponse({"status": "error", "message": "Room code is required"}, status=400)

        user = request.user
        
        # Check if room exists in database
        room = Room.objects.filter(code=room_code).first()
        if not room:
            return JsonResponse({"status": "error", "message": "Room not found"}, status=404)
        
        # Check if user is already in room
        if room.users.filter(id=user.id).exists():
            return JsonResponse({"status": "error", "message": "You are already in this room"}, status=400)
        
        # Verify room in DHT
        dht_room = async_to_sync(get_room_from_dht)(room_code)
        if not dht_room:
            logger.warning(f"Room {room_code} not found in DHT")
        
        # Add user to room
        room.users.add(user)
        
        # Update user profile
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        user_profile.room_code = room_code
        user_profile.save()
        
        # Store room code in session
        request.session['room_code'] = room_code
        
        return JsonResponse({"status": "success", "message": "Joined room successfully", "redirect_url": "/dashboard/"})
        
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"Failed to join room: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


        
    except Exception as e:
        logger.error(f"Failed to join room: {e}")
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@login_required
def room_view(request):
    """Render the room template with user's current room info."""
    try:
        user_profile = UserProfile.objects.filter(user=request.user).first()
        context = {
            'current_room': getattr(user_profile, 'room_code', None)
        }
    except Exception as e:
        logger.error(f"Error in room_view: {e}")
        context = {'current_room': None}
    
    return render(request, "room.html", context)

@login_required
def room_detail(request, room_code):
    """Display detailed room information."""
    try:
        room = Room.objects.filter(code=room_code).first()
        if not room:
            return redirect('room')
        
        # Get DHT room data
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

def leave_room(request):
    """Leave the current room."""
    if request.method == "POST":
        try:
            user_profile = UserProfile.objects.get(user=request.user)
            room_code = user_profile.room_code
            
            if room_code:
                room = Room.objects.get(code=room_code)
                room.users.remove(request.user)
                
                # Clear room code from profile
                user_profile.room_code = None
                user_profile.save()
                
                # Clear session
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

@login_required
def dashboard_view(request):
    # Get current user's profile and room information
    user_profile = UserProfile.objects.get(user=request.user)
    seven_days_ago = timezone.now() - timedelta(days=7)
    
    # Get all users in the same room if user is in a room
    if user_profile.room_code:
        room_users = UserProfile.objects.filter(
            room_code=user_profile.room_code
        ).select_related('user')
    else:
        room_users = UserProfile.objects.filter(is_online=True).select_related('user')

    context = {
        'files_sent': FileTransfer.objects.filter(
            sender=request.user,
            timestamp__gte=seven_days_ago
        ).count(),
        
        'files_received': FileTransfer.objects.filter(
            receiver=request.user,
            timestamp__gte=seven_days_ago
        ).count(),
        
        'malicious_threats': FileTransfer.objects.filter(
            receiver=request.user,
            is_malicious=True,
            timestamp__gte=seven_days_ago
        ).count(),
        
        'notifications': Notification.objects.filter(
            user=request.user,
            is_read=False
        )[:5],
        
        'room_code': user_profile.room_code,
        'room_users': room_users,
        'total_users_in_room': room_users.count()
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def mark_notification_read(request, notification_id):
    Notification.objects.filter(id=notification_id, user=request.user).update(is_read=True)
    return JsonResponse({'status': 'success'})

@login_required
def DashboardPage(request):
    return render(request, 'dashboard.html')

# views.py or wherever you handle Google authentication
def handle_google_login(request, user_info):
    email = user_info.get('email')
    user = User.objects.filter(email=email).first()
    
    if user:
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.google_name = user_info.get('name')  # Save Google name
        profile.save()
        
        login(request, user)
    return redirect('dashboard')