from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DemoMoney
from .serializers import (
    DemoMoneyCreateSerializer,
    DemoMoneySerializer,
    DemoMoneyUpdateSerializer,
)


class DemoMoneyViewSet(viewsets.ViewSet):
    """
    Read/update demo money by user_id.
    """

    def _get_queryset(self):
        return DemoMoney.objects.using("demomoney").all()

    def retrieve(self, request, pk=None):
        try:
            user_id = int(pk)
        except (TypeError, ValueError):
            return Response({"error": "invalid_user_id"}, status=status.HTTP_400_BAD_REQUEST)

        instance = self._get_queryset().filter(user_id=user_id).first()
        if not instance:
            return Response({"error": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = DemoMoneySerializer(instance)
        return Response(serializer.data)

    def create(self, request):
        serializer = DemoMoneyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        amount = serializer.validated_data.get("amount")

        defaults = {}
        if amount is not None:
            defaults["amount"] = amount

        instance, created = DemoMoney.objects.using("demomoney").get_or_create(
            user_id=user_id,
            defaults=defaults,
        )
        return Response(
            DemoMoneySerializer(instance).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def partial_update(self, request, pk=None):
        try:
            user_id = int(pk)
        except (TypeError, ValueError):
            return Response({"error": "invalid_user_id"}, status=status.HTTP_400_BAD_REQUEST)

        instance = self._get_queryset().filter(user_id=user_id).first()
        if not instance:
            return Response({"error": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DemoMoneyUpdateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DemoMoneySerializer(instance).data)

    @action(detail=True, methods=["post"], url_path="reset")
    def reset(self, request, pk=None):
        try:
            user_id = int(pk)
        except (TypeError, ValueError):
            return Response({"error": "invalid_user_id"}, status=status.HTTP_400_BAD_REQUEST)

        instance = self._get_queryset().filter(user_id=user_id).first()
        if not instance:
            return Response({"error": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        instance.amount = "1000.00"
        instance.save(update_fields=["amount"])
        return Response(DemoMoneySerializer(instance).data)
