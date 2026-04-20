"""
URL configuration for decision_service project.

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
from django.contrib import admin
from django.urls import path, include, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from Gameplay.views import unity_game_static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('Decision.urls')),
    path('api/ml/', include('ml.urls')),
    # Merged service apps (mounted under stable prefixes for the admin_portal gateway).
    path('odds/', include('Generator.urls')),
    path('gameplay/', include('Gameplay.urls')),
    path('gameplay/game2/', unity_game_static, {'path': 'index.html', 'game_root_name': 'Game2'}),
    re_path(r'^gameplay/game2/(?P<path>.*)$', unity_game_static, {'game_root_name': 'Game2'}),
    # Compatibility routes for old direct Unity build URLs.
    path('game2/', unity_game_static, {'path': 'index.html', 'game_root_name': 'Game2'}),
    re_path(r'^game2/(?P<path>.*)$', unity_game_static, {'game_root_name': 'Game2'}),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
