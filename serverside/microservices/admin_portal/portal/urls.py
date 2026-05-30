from django.urls import path, re_path
from .views import admin_home
from .views import analytics_embed
from .views import issue_token
from .views import ml_bettor_segments
from .views import unity_game2_proxy

urlpatterns = [
    path("", admin_home, name="admin_home"),
    path("admin/analytics/", analytics_embed, name="admin_analytics_embed"),
    path("admin/ml/bettor-segments/", ml_bettor_segments, name="admin_ml_bettor_segments"),
    path("sso/token/", issue_token, name="issue_token"),
    re_path(r"^game2/(?P<path>.*)$", unity_game2_proxy, name="unity_game2_proxy"),
]
