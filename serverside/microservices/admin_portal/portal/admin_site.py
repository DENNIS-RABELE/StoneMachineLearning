from django.contrib.admin import AdminSite
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from .support_auth import user_is_customer_support


class PortalAdminSite(AdminSite):
    site_header = "Central Admin"
    site_title = "Central Admin"
    index_title = "Microservices"
    index_template = "admin/portal_index.html"

    def has_permission(self, request):
        return (
            super().has_permission(request)
            and request.user.is_superuser
            and not user_is_customer_support(request.user)
        )


site = PortalAdminSite(name="portal_admin")
site.register(User, UserAdmin)
site.register(Group, GroupAdmin)
