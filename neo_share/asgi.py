from channels.routing import ProtocolTypeRouter, URLRouter  # Import routing classes for protocol and URL handling
from channels.auth import AuthMiddlewareStack  # Import middleware for WebSocket authentication
from neo.routing import websocket_urlpatterns  # Import WebSocket URL patterns from neo.routing
from django.core.asgi import get_asgi_application  # Import function to get the Django ASGI application

application = ProtocolTypeRouter({  # Define the root ASGI application using ProtocolTypeRouter
    'http': get_asgi_application(),  # Route HTTP requests to the standard Django ASGI application
    # get_asgi_application() handles traditional Django views (e.g., from neo/views.py)
    
    'websocket': AuthMiddlewareStack(  # Route WebSocket requests through authentication middleware
        URLRouter(  # Use URLRouter to map WebSocket URLs to consumers
            websocket_urlpatterns  # Use patterns defined in neo/routing.py
        )
    ),  # AuthMiddlewareStack adds session and user authentication to WebSocket connections
})