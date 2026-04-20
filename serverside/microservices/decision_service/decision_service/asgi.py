"""
ASGI config for decision_service project.

Decision service hosts:
- HTTP: Decision + Generator + Gameplay endpoints
- WebSocket: Gameplay websocket routes (when available)
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "decision_service.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

try:
    from channels.auth import AuthMiddlewareStack  # noqa: E402
    from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

    from Gameplay.routing import websocket_urlpatterns  # noqa: E402

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        }
    )
except Exception:
    # If channels isn't available or Gameplay isn't importable, fall back to HTTP-only.
    application = django_asgi_app
