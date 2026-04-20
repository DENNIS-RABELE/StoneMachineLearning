from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from Analytics.models import AnalyticsDashboardLink


@admin.register(AnalyticsDashboardLink)
class AnalyticsDashboardLinkAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_staff)

    def changelist_view(self, request, extra_context=None):
        url = reverse("bettor-analytics-dashboard")
        return redirect(f"{url}?range=30")
