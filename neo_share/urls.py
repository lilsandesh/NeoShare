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
from django.contrib import admin
from django.urls import path, include
from neo import views

urlpatterns = [
    path('', views.login_view, name='home'),  # Changed to login_view for root
    path('signup/', views.signup, name='signup'),  # Updated to signup
    path('login/', views.login_view, name='login'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),  # Updated to verify_otp
    path("room/", views.room_view, name="room"),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('admin/', admin.site.urls),
    path('reset-password/confirm/<str:uidb64>/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset-request/', views.password_reset_request, name='password_reset_request'),
    path('social-auth/', include('social_django.urls', namespace='social')),
    path("create-room/", views.create_room, name="create_room"),
    path("join-room/", views.join_room, name="join_room"),
    path("room-view/", views.room_view, name="join-room"),  # Consider removing or renaming for clarity
    path('room/<str:room_code>/', views.room_detail, name='room_detail'),
    path('notification/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('room/leave/', views.leave_room, name='leave_room'),
    path('logout/', views.logout_view, name='logout'),  # Updated from LogoutPage to logout_view
]