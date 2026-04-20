from django.urls import path

from .views import sync_latest_odds_view


urlpatterns = [
    path("api/sync/latest-odds/", sync_latest_odds_view, name="sync-latest-odds"),
]
