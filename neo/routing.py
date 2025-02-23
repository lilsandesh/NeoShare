# routing.py

from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'ws/live_users/$', consumers.LiveUserConsumer.as_asgi()),
    re_path(r'ws/signaling/$', consumers.FileTransferConsumer.as_asgi()),

]