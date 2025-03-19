from django.urls import re_path  # Import re_path for regex-based URL patterns
from channels.routing import ProtocolTypeRouter, URLRouter  # Import routing classes for Channels (unused here but likely in broader context)
from channels.auth import AuthMiddlewareStack  # Import AuthMiddlewareStack for authentication (unused here but likely in broader context)
from . import consumers  # Import consumers module from the current app

websocket_urlpatterns = [  # Define a list of WebSocket URL patterns
    re_path(r'ws/dashboard/(?P<room_code>[^/]+)/$', consumers.DashboardConsumer.as_asgi()),  # Route for dashboard WebSocket with room_code
    # Pattern matches URLs like ws/dashboard/abc123/, capturing room_code as a named group
    # [^/]+ means one or more characters that aren’t a slash
    # Routes to DashboardConsumer, converted to ASGI application with as_asgi()

    re_path(r'ws/live_users/$', consumers.LiveUserConsumer.as_asgi()),  # Route for live users WebSocket
    # Pattern matches ws/live_users/ exactly (no parameters)
    # Routes to LiveUserConsumer, converted to ASGI application with as_asgi()

    re_path(r'ws/signaling/$', consumers.FileTransferConsumer.as_asgi()),  # Route for signaling WebSocket
    # Pattern matches ws/signaling/ exactly (no parameters)
    # Routes to FileTransferConsumer, converted to ASGI application with as_asgi()
]