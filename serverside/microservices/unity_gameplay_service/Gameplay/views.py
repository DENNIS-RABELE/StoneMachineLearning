import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .broadcast import broadcast_mirror
from .models import UnityGameConfig
from .state import (
    get_global_gameplay_state,
    publish_snapshot,
    reset_gameplay,
    serialize_state,
    start_gameplay,
    stop_gameplay,
)

def _dashboard_admin_redirect():
    return redirect("/admin/Gameplay/unitygameplaydashboardlink/")

def _service_base_url(request) -> str:
    port = os.getenv("PORT", "8001")
    base_path = str(getattr(settings, "UNITY_GAMEPLAY_BASE_PATH", "") or "").rstrip("/")
    return f"http://127.0.0.1:{port}{base_path}"

def _get_active_build_url():
    active_config = UnityGameConfig.objects.filter(is_active=True).order_by("-updated_at").first()
    if active_config and active_config.build_url:
        return active_config.build_url.strip()
    return getattr(settings, "UNITY_WEBGL_BUILD_URL", "").strip() or "/game2/"

def _unity_context():
    state = serialize_state(get_global_gameplay_state())
    unity_build_url = _get_active_build_url()
    gameplay_running = str(state.get("status") or "").upper() == "RUNNING"
    return {
        "state": state,
        "unity_build_url": unity_build_url,
        "unity_embed_src": "./index.html",
        "unity_embed_enabled": bool(unity_build_url),
        "gameplay_running": gameplay_running,
        "unity_display_enabled": bool(unity_build_url) and gameplay_running,
        "client_origin": os.getenv("CLIENT_SITE_ORIGIN", "http://localhost:3000"),
        "gameplay_ws_url": "/ws/gameplay/",
    }

def _ensure_broadcast_started(request) -> dict:
    source_url = f"{_service_base_url(request)}/broadcast/source/"
    broadcast_mirror.ensure_started(source_url)
    return broadcast_mirror.status()

def unity_host_view(request):
    context = _unity_context()
    return render(request, "unity_gameplay/unity_host.html", context)

@xframe_options_exempt
def unity_embed_view(request):
    context = _unity_context()
    return render(request, "unity_gameplay/unity_embed.html", context)

@xframe_options_exempt
def unity_embed_static(request, path):
    return unity_game_static(request, path=path, game_root_name="Game2")

def unity_embed_meta(request):
    context = _unity_context()
    return JsonResponse({
        "active_build_url": context["unity_build_url"],
        "active_game_root": "Game2",
        "state": context["state"],
        "unity_embed_enabled": context["unity_embed_enabled"],
        "unity_display_enabled": context["unity_display_enabled"],
    })

@xframe_options_exempt
def unity_broadcast_source(request):
    html = "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>Broadcast Source</body></html>"
    return HttpResponse(html)

@xframe_options_exempt
def unity_broadcast_view(request):
    _ensure_broadcast_started(request)
    html = "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>Broadcast Viewer</body></html>"
    return HttpResponse(html)

def unity_broadcast_meta(request):
    status = _ensure_broadcast_started(request)
    status["active_build_url"] = _get_active_build_url()
    status["active_game_root"] = "Game2"
    return JsonResponse(status)

def unity_broadcast_frame(request):
    _ensure_broadcast_started(request)
    frame, _, _, error = broadcast_mirror.latest_frame()
    if not frame:
        return JsonResponse({"error": error or "Broadcast frame is not ready yet."}, status=503)
    response = HttpResponse(frame, content_type="image/jpeg")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@xframe_options_exempt
def unity_broadcast_stream(request):
    _ensure_broadcast_started(request)

    def event_stream():
        last_seen_id = 0
        boundary = b"--frame\r\n"
        while True:
            frame, frame_id = broadcast_mirror.wait_for_next_frame(last_seen_id, timeout=10.0)
            if not frame:
                continue
            last_seen_id = frame_id
            yield boundary
            yield b"Content-Type: image/jpeg\r\n"
            yield f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
            yield frame
            yield b"\r\n"

    response = StreamingHttpResponse(event_stream(), content_type="multipart/x-mixed-replace; boundary=frame")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response

@staff_member_required
def unity_admin_dashboard(request):
    context = _unity_context()
    context["unity_embed_route"] = reverse("unity-embed")
    context["game_configs"] = UnityGameConfig.objects.order_by("-updated_at")
    context["control_url"] = reverse("unity-gameplay-control")
    context["config_activate_url"] = reverse("unity-gameplay-config-activate")
    return render(request, "unity_gameplay/admin_dashboard.html", context)

def gameplay_state_snapshot(request):
    return JsonResponse(serialize_state(get_global_gameplay_state()))

@csrf_exempt
@staff_member_required
def gameplay_control(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    action = str(request.POST.get("action", "")).strip().lower()
    max_ticks_raw = str(request.POST.get("max_ticks", "")).strip()
    max_ticks = int(max_ticks_raw) if max_ticks_raw.isdigit() else None

    if action == "start":
        start_gameplay(max_ticks=max_ticks, reset_tick=False)
    elif action == "restart":
        start_gameplay(max_ticks=max_ticks, reset_tick=True)
    elif action == "stop":
        stop_gameplay()
    elif action == "reset":
        reset_gameplay(max_ticks=max_ticks)
    elif action == "publish":
        publish_snapshot()

    return _dashboard_admin_redirect()

@csrf_exempt
@staff_member_required
def set_active_game_config(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    config_id_raw = str(request.POST.get("config_id", "")).strip()
    if not config_id_raw.isdigit():
        return _dashboard_admin_redirect()

    config_id = int(config_id_raw)
    with transaction.atomic():
        UnityGameConfig.objects.filter(is_active=True).update(is_active=False)
        UnityGameConfig.objects.filter(id=config_id).update(is_active=True)

    return _dashboard_admin_redirect()

@xframe_options_exempt
def unity_game_static(request, path="index.html", game_root_name="Game2"):
    # Works both standalone and when embedded into another Django project.
    service_root = Path(__file__).resolve().parent.parent
    game_root = (service_root / game_root_name).resolve()
    requested = (game_root / path).resolve()

    if not str(requested).startswith(str(game_root)):
        raise Http404("Invalid path.")
    if requested.is_dir():
        requested = requested / "index.html"
    if not requested.exists():
        raise Http404("File not found.")

    content_types = {
        ".html": "text/html", ".js": "application/javascript", ".css": "text/css",
        ".wasm": "application/wasm", ".data": "application/octet-stream",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".ico": "image/x-icon", ".json": "application/json",
    }

    # Unity WebGL often produces pre-compressed artifacts:
    # - *.wasm.unityweb, *.data.unityweb, *.framework.js.unityweb
    # Some Unity exports (when "Decompression Fallback" is enabled) wrap the
    # payload in a "UnityWeb Compressed Content (...)" container. Those files
    # must NOT be served with an HTTP Content-Encoding header, because the
    # browser would try to decompress bytes that are not a raw gzip/br stream.
    encoding = None
    suffixes = [s.lower() for s in requested.suffixes]
    if suffixes and suffixes[-1] == ".unityweb":
        inner_suffix = suffixes[-2] if len(suffixes) >= 2 else ""
        content_type = content_types.get(inner_suffix, "application/octet-stream")

        # Auto-detect whether this .unityweb is a raw gzip stream (server must set
        # Content-Encoding: gzip) or a Unity "decompression fallback" container
        # (server must NOT set Content-Encoding).
        #
        # gzip magic bytes: 1F 8B
        # Unity container includes the ASCII marker "UnityWeb" near the start.
        try:
            with open(requested, "rb") as f:
                head = f.read(64)
            if head.startswith(b"\x1f\x8b"):
                encoding = "gzip"
            elif b"UnityWeb" in head:
                encoding = None
        except OSError:
            encoding = None
    else:
        content_type = content_types.get(requested.suffix.lower(), "application/octet-stream")

    response = FileResponse(open(requested, "rb"), content_type=content_type)
    if encoding:
        response["Content-Encoding"] = encoding
        response["Vary"] = "Accept-Encoding"
    response["X-Frame-Options"] = "SAMEORIGIN"
    response["Cache-Control"] = "no-cache"
    return response
