from django.urls import path, re_path
from .views import (
    gameplay_control,
    gameplay_state_snapshot,
    set_active_game_config,
    unity_admin_dashboard,
    unity_broadcast_frame,
    unity_broadcast_meta,
    unity_broadcast_source,
    unity_broadcast_stream,
    unity_broadcast_view,
    unity_embed_meta,
    unity_embed_view,
    unity_embed_static,
    unity_host_view,
)

urlpatterns = [
    path("", unity_host_view, name="unity-host"),
    path("embed/", unity_embed_view, name="unity-embed"),
    path("embed-meta/", unity_embed_meta, name="unity-embed-meta"),
    re_path(r"^embed/(?P<path>.*)$", unity_embed_static, name="unity-embed-static"),
    path("broadcast/source/", unity_broadcast_source, name="unity-broadcast-source"),
    path("broadcast/view/", unity_broadcast_view, name="unity-broadcast-view"),
    path("broadcast/meta/", unity_broadcast_meta, name="unity-broadcast-meta"),
    path("broadcast/frame.jpg", unity_broadcast_frame, name="unity-broadcast-frame"),
    path("broadcast/stream.mjpg", unity_broadcast_stream, name="unity-broadcast-stream"),
    path("dashboard/", unity_admin_dashboard, name="unity-gameplay-dashboard"),
    path("state/", gameplay_state_snapshot, name="unity-gameplay-state"),
    path("control/", gameplay_control, name="unity-gameplay-control"),
    path("config/activate/", set_active_game_config, name="unity-gameplay-config-activate"),
    path("admin/config/activate/", set_active_game_config, name="unity-gameplay-config-activate-admin"),
]