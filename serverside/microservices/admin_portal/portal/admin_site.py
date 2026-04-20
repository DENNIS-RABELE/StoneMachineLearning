from django.contrib.admin import AdminSite
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User


class PortalAdminSite(AdminSite):
    site_header = "Central Admin"
    site_title = "Central Admin"
    index_title = "Microservices"
    index_template = "admin/portal_index.html"


site = PortalAdminSite(name="portal_admin")
site.register(User, UserAdmin)
site.register(Group, GroupAdmin)
