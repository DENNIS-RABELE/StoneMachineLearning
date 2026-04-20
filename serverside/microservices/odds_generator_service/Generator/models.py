from django.db import models


class BetOdds(models.Model):
    character_id = models.BigIntegerField(db_index=True)

    drn1 = models.DecimalField(max_digits=4, decimal_places=2)
    drn2 = models.DecimalField(max_digits=4, decimal_places=2)
    drn3 = models.DecimalField(max_digits=4, decimal_places=2)
    drn4 = models.DecimalField(max_digits=4, decimal_places=2)
    drn5 = models.DecimalField(max_digits=4, decimal_places=2)

    flt1 = models.DecimalField(max_digits=4, decimal_places=2)
    flt2 = models.DecimalField(max_digits=4, decimal_places=2)
    flt3 = models.DecimalField(max_digits=4, decimal_places=2)
    flt4 = models.DecimalField(max_digits=4, decimal_places=2)
    flt5 = models.DecimalField(max_digits=4, decimal_places=2)

    flt1_and_drn2 = models.DecimalField(max_digits=4, decimal_places=2)
    flt1_and_drn3 = models.DecimalField(max_digits=4, decimal_places=2)
    flt1_and_drn4 = models.DecimalField(max_digits=4, decimal_places=2)
    flt1_and_drn5 = models.DecimalField(max_digits=4, decimal_places=2)
    flt2_and_drn3 = models.DecimalField(max_digits=4, decimal_places=2)
    flt2_and_drn4 = models.DecimalField(max_digits=4, decimal_places=2)
    flt2_and_drn5 = models.DecimalField(max_digits=4, decimal_places=2)
    flt3_and_drn4 = models.DecimalField(max_digits=4, decimal_places=2)
    flt3_and_drn5 = models.DecimalField(max_digits=4, decimal_places=2)
    flt4_and_drn5 = models.DecimalField(max_digits=4, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bet_odds"
        constraints = [
            models.UniqueConstraint(fields=["character_id"], name="uniq_bet_odds_character")
        ]

    def __str__(self):
        return f"{self.character_id} odds"
