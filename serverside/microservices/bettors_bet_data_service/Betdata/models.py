from django.db import models
from django.db.models import Q, F

class BetType(models.TextChoices):
    SINGLE = "SINGLE", "Single"
    DOUBLE = "DOUBLE", "Double"

class BetStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"

class OutcomeKind(models.TextChoices):
    FLOAT = "FLOAT", "Float"
    DROWN = "DROWN", "Drown"

class RoundStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"

class WalletTxType(models.TextChoices):
    BET_STAKE = "BET_STAKE", "Bet Stake"
    BET_PAYOUT = "BET_PAYOUT", "Bet Payout"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"

class WalletAccountType(models.TextChoices):
    PLAYER = "PLAYER", "Player"
    HOUSE = "HOUSE", "House"
    SYSTEM = "SYSTEM", "System"

class SlipStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"
    SETTLED = "SETTLED", "Settled"

class GameRound(models.Model):
    round_id = models.BigIntegerField(unique=True, db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=12,
        choices=RoundStatus.choices,
        default=RoundStatus.OPEN,
        db_index=True,
    )

    class Meta:
        db_table = "client_game_round"
        ordering = ["-round_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=[RoundStatus.OPEN, RoundStatus.CLOSED]),
                name="chk_client_game_round_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_time__isnull=True) | Q(end_time__gte=F("start_time")),
                name="chk_client_game_round_end_after_start_or_null",
            ),
            models.UniqueConstraint(
                fields=["status"],
                condition=Q(status=RoundStatus.OPEN),
                name="uniq_client_game_round_single_open",
            ),
        ]

    def __str__(self):
        return f"Round {self.round_id} ({self.status})"

class Phase(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=32)

    class Meta:
        db_table = "client_phase"
        ordering = ["number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(number__gte=1) & Q(number__lte=5),
                name="chk_client_phase_number_range_1_5",
            )
        ]

    def __str__(self):
        return f"Phase {self.number} - {self.name}"

class Outcome(models.Model):
    external_outcome_id = models.PositiveIntegerField(unique=True, db_index=True)
    phase_id = models.PositiveSmallIntegerField(db_index=True)
    kind = models.CharField(max_length=8, choices=OutcomeKind.choices)
    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=64)

    class Meta:
        db_table = "client_outcome"
        ordering = ["external_outcome_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["phase_id", "kind"],
                name="uniq_client_outcome_phase_kind",
            )
        ]

    def __str__(self):
        return f"{self.code} ({self.label})"

class Bet(models.Model):
    player_id = models.BigIntegerField(db_index=True)
    character = models.PositiveIntegerField()
    game_round = models.PositiveIntegerField()
    slip_id = models.UUIDField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=12,
        choices=BetStatus.choices,
        default=BetStatus.OPEN,
        db_index=True,
    )
    bet_type = models.CharField(max_length=8, choices=BetType.choices, db_index=True)
    option_code = models.CharField(max_length=16, db_index=True)
    phase_start = models.PositiveSmallIntegerField(db_index=True)
    phase_end = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    stake = models.DecimalField(max_digits=12, decimal_places=2)
    odds = models.DecimalField(max_digits=8, decimal_places=2)
    placed_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client_bet"
        ordering = ["-placed_at", "-id"]
        indexes = [
            models.Index(fields=["player_id", "placed_at"], name="idx_client_bet_player_ts"),
            models.Index(fields=["bet_type", "placed_at"], name="idx_client_bet_type_ts"),
            models.Index(fields=["status", "placed_at"], name="idx_client_bet_status_ts"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=[BetStatus.OPEN, BetStatus.CLOSED]),
                name="chk_client_bet_status_valid",
            ),
            models.CheckConstraint(condition=Q(stake__gt=0), name="chk_client_bet_stake_gt_0"),
            models.CheckConstraint(condition=Q(odds__gt=1), name="chk_client_bet_odds_gt_1"),
            models.CheckConstraint(
                condition=Q(phase_start__gte=1) & Q(phase_start__lte=5),
                name="chk_client_bet_phase_start_range_1_5",
            ),
            models.CheckConstraint(
                condition=Q(phase_end__isnull=True) | (Q(phase_end__gte=1) & Q(phase_end__lte=5)),
                name="chk_client_bet_phase_end_range_1_5_or_null",
            ),
            models.CheckConstraint(
                condition=Q(phase_end__isnull=True) | Q(phase_end__gt=F("phase_start")),
                name="chk_client_bet_phase_end_gt_start",
            ),
        ]

    def __str__(self):
        return f"Bet {self.id} | player={self.player_id} | type={self.bet_type} | stake={self.stake} | odds={self.odds}"

class BetOutcome(models.Model):
    bet_id = models.BigIntegerField(db_index=True)
    outcome_id = models.PositiveIntegerField(db_index=True)
    selection_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "client_bet_outcome"
        ordering = ["bet_id", "selection_order"]
        constraints = [
            models.UniqueConstraint(fields=["bet_id", "selection_order"], name="uniq_client_bet_outcome_order"),
            models.UniqueConstraint(fields=["bet_id", "outcome_id"], name="uniq_client_bet_outcome_pair"),
            models.CheckConstraint(condition=Q(selection_order__gte=1), name="chk_client_bet_outcome_order_gte_1"),
        ]

    def __str__(self):
        return f"Bet {self.bet_id} -> Outcome {self.outcome_id} (order {self.selection_order})"

class PlayerWallet(models.Model):
    player_id = models.BigIntegerField(unique=True, db_index=True)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client_player_wallet"
        ordering = ["player_id"]
        constraints = [
            models.CheckConstraint(condition=Q(balance__gte=0), name="chk_client_player_wallet_balance_non_negative"),
        ]

    def __str__(self):
        return f"PlayerWallet player={self.player_id} balance={self.balance}"

class HouseWallet(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client_house_wallet"
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="chk_client_house_wallet_singleton_id_1"),
        ]

    def __str__(self):
        return f"HouseWallet balance={self.balance}"

class WalletTransaction(models.Model):
    game_round_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    bet_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    player_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    tx_type = models.CharField(max_length=16, choices=WalletTxType.choices, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    from_account = models.CharField(max_length=8, choices=WalletAccountType.choices)
    to_account = models.CharField(max_length=8, choices=WalletAccountType.choices)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "client_wallet_transaction"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tx_type", "created_at"], name="idx_client_wallet_tx_type_ts"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="chk_client_wallet_tx_amount_gt_0"),
        ]

    def __str__(self):
        return f"WalletTx {self.id} {self.tx_type} amount={self.amount} {self.from_account}->{self.to_account}"

class Slip(models.Model):
    player_id = models.BigIntegerField(db_index=True)
    game_round = models.PositiveIntegerField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=SlipStatus.choices,
        default=SlipStatus.OPEN,
        db_index=True,
    )
    total_stake = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_possible_win = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    placed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client_slip"
        ordering = ["-placed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["player_id", "game_round"], name="uniq_client_slip_player_round"),
            models.CheckConstraint(condition=Q(total_stake__gte=0), name="chk_client_slip_total_stake_non_negative"),
            models.CheckConstraint(condition=Q(total_possible_win__gte=0), name="chk_client_slip_total_possible_win_non_negative"),
        ]

    def __str__(self):
        return f"Slip {self.id} player={self.player_id} round={self.game_round}"

class SlipItem(models.Model):
    slip_id = models.BigIntegerField(db_index=True)
    bet_id = models.BigIntegerField(unique=True, db_index=True)
    character = models.PositiveIntegerField(db_index=True)
    bet_type = models.CharField(max_length=8, choices=BetType.choices, db_index=True)
    option_code = models.CharField(max_length=16, db_index=True)
    phase_start = models.PositiveSmallIntegerField(db_index=True)
    phase_end = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    stake = models.DecimalField(max_digits=12, decimal_places=2)
    odds = models.DecimalField(max_digits=8, decimal_places=2)
    possible_win = models.DecimalField(max_digits=14, decimal_places=2)
    placed_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client_slip_item"
        ordering = ["placed_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(stake__gt=0), name="chk_client_slip_item_stake_gt_0"),
            models.CheckConstraint(condition=Q(odds__gt=0), name="chk_client_slip_item_odds_gt_0"),
            models.CheckConstraint(condition=Q(possible_win__gte=0), name="chk_client_slip_item_possible_win_non_negative"),
        ]

    def __str__(self):
        return f"SlipItem {self.id} slip={self.slip_id} bet={self.bet_id}"

class SlipItemMarket(models.Model):
    slip_item_id = models.BigIntegerField(db_index=True)
    market_id = models.BigIntegerField(db_index=True)
    outcome_id = models.PositiveIntegerField(db_index=True)
    phase_number = models.PositiveSmallIntegerField(db_index=True)
    stake_portion = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client_slip_item_market"
        ordering = ["slip_item_id", "phase_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["slip_item_id", "market_id", "outcome_id"],
                name="uniq_client_slip_item_market_outcome",
            ),
            models.CheckConstraint(condition=Q(stake_portion__gt=0), name="chk_client_slip_item_market_stake_portion_gt_0"),
        ]

    def __str__(self):
        return f"SlipItemMarket slip_item={self.slip_item_id} market={self.market_id}"