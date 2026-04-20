from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class RoundStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"


class GameRound(models.Model):
    round_id = models.PositiveIntegerField(unique=True)
    status = models.CharField(max_length=16, choices=RoundStatus.choices)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Round {self.round_id} ({self.status})"


class DecisionRoundStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"


class DecisionRound(models.Model):
    status = models.CharField(
        max_length=16,
        choices=DecisionRoundStatus.choices,
        default=DecisionRoundStatus.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rounds"

    def __str__(self):
        return f"decision-round:{self.pk} ({self.status})"


class Phase(models.Model):
    round = models.ForeignKey(
        DecisionRound,
        on_delete=models.CASCADE,
        related_name="phases",
    )
    phase_number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        db_table = "phases"
        constraints = [
            models.UniqueConstraint(
                fields=["round", "phase_number"],
                name="uniq_round_phase_number",
            )
        ]
        ordering = ["round_id", "phase_number"]

    def __str__(self):
        return f"round:{self.round_id}:phase:{self.phase_number}"




class Bet_decision(models.Model):
    round_result = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} | {self.round_result} | {self.created_at}"


class Character(models.Model):
    name = models.CharField(max_length=60, unique=True)

    stamina = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    control = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    power = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def clean_name(self):
        # safer: only split once
        return self.name.split("_", 1)[0]

    def __str__(self):
        return self.clean_name


class Outcome(models.Model):
    class Code(models.TextChoices):
        FLOAT = "FLOAT", "Float"
        DROWN = "DROWN", "Drown"

    code = models.CharField(max_length=10, choices=Code.choices, unique=True)

    class Meta:
        db_table = "outcomes"

    def __str__(self):
        return self.code


class PhaseCharacterMarket(models.Model):
    round = models.ForeignKey(
        DecisionRound,
        on_delete=models.CASCADE,
        related_name="markets",
    )
    phase = models.ForeignKey(
        Phase,
        on_delete=models.CASCADE,
        related_name="markets",
    )
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="markets",
    )

    class Meta:
        db_table = "phase_character_market"
        constraints = [
            models.UniqueConstraint(
                fields=["round", "phase", "character"],
                name="uniq_round_phase_character_market",
            )
        ]

    def __str__(self):
        return f"market:{self.pk} r{self.round_id} p{self.phase_id} c{self.character_id}"


class MarketOdds(models.Model):
    market = models.ForeignKey(
        PhaseCharacterMarket,
        on_delete=models.CASCADE,
        related_name="odds",
    )
    outcome = models.ForeignKey(
        Outcome,
        on_delete=models.CASCADE,
        related_name="market_odds",
    )
    current_odds = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        db_table = "market_odds"
        constraints = [
            models.UniqueConstraint(
                fields=["market", "outcome"],
                name="uniq_market_outcome_odds",
            )
        ]

    def __str__(self):
        return f"market:{self.market_id} {self.outcome.code}={self.current_odds}"


class RoundMarketOutcome(models.Model):
    client_round_id = models.BigIntegerField(db_index=True)
    decision_round = models.ForeignKey(
        DecisionRound,
        on_delete=models.CASCADE,
        related_name="resolved_outcomes",
    )
    market = models.ForeignKey(
        PhaseCharacterMarket,
        on_delete=models.CASCADE,
        related_name="resolved_outcomes",
    )
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="round_outcomes",
    )
    outcome = models.ForeignKey(
        Outcome,
        on_delete=models.PROTECT,
        related_name="round_market_outcomes",
        null=True,
        blank=True,
    )
    phase_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "round_market_outcome"
        ordering = ["-client_round_id", "character_id", "phase_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["client_round_id", "character", "phase_number"],
                name="uniq_client_round_character_phase_outcome",
            ),
            models.UniqueConstraint(
                fields=["client_round_id", "market"],
                name="uniq_client_round_market_outcome",
            ),
        ]

    def __str__(self):
        return (
            f"client_round:{self.client_round_id} "
            f"character:{self.character_id} "
            f"phase:{self.phase_number} "
            f"outcome:{self.outcome_id or 'NULL'}"
        )
