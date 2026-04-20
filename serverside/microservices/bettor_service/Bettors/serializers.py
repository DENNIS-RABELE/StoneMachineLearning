from rest_framework import serializers

from .models import DemoMoney


class DemoMoneySerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoMoney
        fields = ("id", "user_id", "amount", "created_at", "updated_at")
        read_only_fields = ("id", "user_id", "created_at", "updated_at")


class DemoMoneyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoMoney
        fields = ("amount",)


class DemoMoneyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoMoney
        fields = ("user_id", "amount")
