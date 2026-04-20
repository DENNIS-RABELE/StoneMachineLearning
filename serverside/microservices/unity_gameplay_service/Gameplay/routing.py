from django.urls import re_path
from .consumers import GlobalGameplayConsumer

websocket_urlpatterns = [
    re_path(r"^ws/gameplay/?$", GlobalGameplayConsumer.as_asgi()),
]