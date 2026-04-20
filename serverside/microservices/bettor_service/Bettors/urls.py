from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DemoMoneyViewSet


router = DefaultRouter()
router.register(r"demomoney", DemoMoneyViewSet, basename="demomoney")

urlpatterns = [
    path("", include(router.urls)),
]
