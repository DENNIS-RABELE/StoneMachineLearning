"""
URL configuration for admin_portal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from portal.admin_site import site as portal_admin_site
from portal import views as portal_views
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from gateway import views as gateway_views

service_ids = '|'.join(gateway_views.MICROSERVICES.keys())
admin_service_pattern = rf'^admin/(?P<service_id>({service_ids}))/(?P<path>.*)$'
embed_service_pattern = rf'^embed/(?P<service_id>({service_ids}))/(?P<path>.*)$'

urlpatterns = [
    path("admin/analytics/", portal_views.analytics_embed, name="admin-analytics-embed"),
    re_path(embed_service_pattern, gateway_views.forward_embed_service, name="embed-service-proxy"),
    re_path(
        admin_service_pattern,
        csrf_exempt(gateway_views.forward_admin_service),
        name="admin-service-proxy",
    ),
    path("admin/", portal_admin_site.urls),
    path("accounts/login/", RedirectView.as_view(url="/admin/login/")),
    path("", include("portal.urls")),
    # API Gateway
    path("api/", include("gateway.urls")),
    # OpenAPI Schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
