from rest_framework import serializers


class BetSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    player_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField(default='pending')
    created_at = serializers.DateTimeField(read_only=True)


class RoundStatusSerializer(serializers.Serializer):
    round_id = serializers.IntegerField(read_only=True)
    status = serializers.ChoiceField(choices=['waiting', 'betting', 'deciding', 'closed'])
    time_remaining = serializers.IntegerField(help_text="seconds")
    total_bets = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
