from django.db import models
from decimal import Decimal

# Create your models here.

class Bettors(models.Model):
    
    firstname = models.CharField(max_length=60)
    lastname = models.CharField(max_length=60)
    email = models.EmailField( null=True, blank=True)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=60)
    id_number = models.BigIntegerField()
    physical_address = models.TextField()
    password_hash = models.CharField(max_length=128)
    
    
    
    def __str__(self):
        return (f"ID: {self.id} Firstname: {self.firstname} Lastname: {self.lastname}"
                f" Date of birth: {self.date_of_birth} Nationality: {self.nationality} ID Nmber: {self.id_number}"
                f" Physical address: {self.physical_address}")


class DemoMoney(models.Model):
    user_id = models.BigIntegerField(unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1000.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "demo_money"

    def __str__(self):
        return f"User {self.user_id} balance {self.amount}"


class BettorActivityEvent(models.Model):
    id = models.BigAutoField(primary_key=True, serialize=False)
    bettor_id = models.BigIntegerField(db_index=True)
    event_type = models.CharField(max_length=32, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "bettor_activity_event"
        indexes = [
            models.Index(fields=["bettor_id", "created_at"], name="idx_bettor_activity_user_ts"),
            models.Index(fields=["event_type", "created_at"], name="idx_bettor_activity_type_ts"),
        ]

    def __str__(self):
        return f"Bettor {self.bettor_id} {self.event_type} at {self.created_at}"

