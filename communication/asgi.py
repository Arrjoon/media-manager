import os
import django
from django.core.asgi import get_asgi_application

# Must be set **before any Django import that uses models**
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'communication.settings')

# Setup Django BEFORE importing anything else that uses models
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from accounts.middleware.jwt_middleware import JWTAuthMiddleware
from chat.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})