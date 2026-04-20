from django.urls import path

from Analytics.views import analytics_dashboard


urlpatterns = [
    path("", analytics_dashboard, name="bettor-analytics-dashboard"),
]
