from django.contrib import admin
from django.urls import reverse
from .models import GlobalGameplayState, UnityGameConfig, UnityGameplayDashboardLink
from .state import get_global_gameplay_state, serialize_state
from .views import _unity_context

@admin.register(UnityGameConfig)
class UnityGameConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "build_url", "is_active", "updated_at")
    list_filter = ("is_active", "updated_at")
    search_fields = ("name", "build_url")
    ordering = ("-updated_at",)

@admin.register(UnityGameplayDashboardLink)
class UnityGameplayDashboardLinkAdmin(admin.ModelAdmin):
    change_list_template = "admin/Gameplay/unitygameplaydashboardlink/change_list.html"

    def changelist_view(self, request, extra_context=None):
        context = _unity_context()
        forwarded_host = str(request.META.get("HTTP_X_FORWARDED_HOST") or "").strip().lower()
        current_host = str(request.get_host() or "").strip().lower()
        via_admin_portal = bool(
            forwarded_host and forwarded_host != current_host
        ) or current_host.endswith(":9006") or forwarded_host.endswith(":9006")
        is_proxied_decision_admin = request.path.startswith("/admin/decision/")
        is_direct_gameplay_admin = request.path.startswith("/admin/gameplay/")

        context["unity_embed_route"] = (
            "/embed/decision/gameplay/embed/"
            if is_proxied_decision_admin or via_admin_portal
            else reverse("unity-embed")
        )
        context["state"] = serialize_state(get_global_gameplay_state())
        context["game_configs"] = UnityGameConfig.objects.order_by("-updated_at")

        if is_proxied_decision_admin or via_admin_portal:
            context["control_url"] = "/admin/decision/control/"
        elif is_direct_gameplay_admin:
            context["control_url"] = "/admin/gameplay/control/"
        else:
            context["control_url"] = reverse("unity-gameplay-control")

        if extra_context:
            context.update(extra_context)
        return super().changelist_view(request, extra_context=context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_staff)

    def get_queryset(self, request):
        return self.model.objects.none()

@admin.register(GlobalGameplayState)
class GlobalGameplayStateAdmin(admin.ModelAdmin):
    list_display = ("key", "status", "tick", "max_ticks", "updated_at")
    readonly_fields = ("updated_at", "started_at", "stopped_at")

    def has_add_permission(self, request):
        return False
