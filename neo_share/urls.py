"""
URL configuration for neo_share project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin  # Import Django admin module
from django.urls import path, include  # Import path and include for URL routing
from neo import views  # Import views module from neo app

urlpatterns = [  # List of URL patterns
    path('', views.login_view, name='home'),  # Root URL ('/') routes to login_view as the homepage
    # Named 'home' for reverse URL resolution

    path('signup/', views.signup, name='signup'),  # URL for signup page, routes to signup view
    # Named 'signup' for reverse URL resolution

    path('login/', views.login_view, name='login'),  # URL for login page, routes to login_view
    # Named 'login' for reverse URL resolution

    path('verify-otp/', views.verify_otp, name='verify_otp'),  # URL for OTP verification, routes to verify_otp view
    # Named 'verify_otp' for reverse URL resolution

    path("room/", views.room_view, name="room"),  # URL for room selection page, routes to room_view
    # Named 'room' for reverse URL resolution

    path('dashboard/', views.dashboard_view, name='dashboard'),  # URL for dashboard, routes to dashboard_view
    # Named 'dashboard' for reverse URL resolution

    path('admin/', admin.site.urls),  # URL for Django admin interface
    # Uses admin.site.urls provided by Django

    path('reset-password/confirm/<str:uidb64>/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),  # URL for password reset confirmation
    # Captures uidb64 and token as string parameters, routes to password_reset_confirm
    # Named 'password_reset_confirm' for reverse URL resolution

    path('password-reset-request/', views.password_reset_request, name='password_reset_request'),  # URL for password reset request, routes to password_reset_request
    # Named 'password_reset_request' for reverse URL resolution

    path('social-auth/', include('social_django.urls', namespace='social')),  # URL for social auth (e.g., Google OAuth2)
    # Includes social_django URLs with 'social' namespace

    path("create-room/", views.create_room, name="create_room"),  # URL for creating a room, routes to create_room
    # Named 'create_room' for reverse URL resolution

    path("join-room/", views.join_room, name="join_room"),  # URL for joining a room, routes to join_room
    # Named 'join_room' for reverse URL resolution

    path("room-view/", views.room_view, name="join-room"),  # URL for room view, routes to room_view (potential duplicate)
    # Named 'join-room' (conflicts with join_room naming; consider revising)

    path('room/<str:room_code>/', views.room_detail, name='room_detail'),  # URL for room details, captures room_code
    # Routes to room_detail view, named 'room_detail' for reverse URL resolution

    path('notification/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),  # URL for marking notification as read
    # Captures notification_id as an integer, routes to mark_notification_read
    # Named 'mark_notification_read' for reverse URL resolution

    path('room/leave/', views.leave_room, name='leave_room'),  # URL for leaving a room, routes to leave_room
    # Named 'leave_room' for reverse URL resolution

    path('logout/', views.logout_view, name='logout'),  # URL for logout, routes to logout_view
    # Named 'logout' for reverse URL resolution

    path('google-login/', views.google_login_with_recaptcha, name='google_login_with_recaptcha'),  # URL for Google login with reCAPTCHA
    # Routes to google_login_with_recaptcha, named 'google_login_with_recaptcha' for reverse URL resolution

    path('scan-file/', views.scan_file, name='scan_file'),  # URL for file scanning endpoint
    # Routes to scan_file view, named 'scan_file' for reverse URL resolution
]