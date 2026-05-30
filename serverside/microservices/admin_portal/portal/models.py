from django.conf import settings
from django.db import models


class SupportEnquiry(models.Model):
    STATUS_OPEN = "open"
    STATUS_ANSWERED = "answered"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ANSWERED, "Answered"),
        (STATUS_CLOSED, "Closed"),
    ]

    CATEGORY_ACCOUNT = "account"
    CATEGORY_BETTING = "betting"
    CATEGORY_PAYMENT = "payment"
    CATEGORY_COMPLAINT = "complaint"
    CATEGORY_SUGGESTION = "suggestion"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_ACCOUNT, "Account Issue"),
        (CATEGORY_BETTING, "Betting Question"),
        (CATEGORY_PAYMENT, "Payment Question"),
        (CATEGORY_COMPLAINT, "Complaint"),
        (CATEGORY_SUGGESTION, "Suggestion"),
        (CATEGORY_OTHER, "Other"),
    ]

    bettor_id = models.BigIntegerField(db_index=True)
    bettor_email = models.EmailField(blank=True)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    support_response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_responses",
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_support_enquiry"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["bettor_id", "created_at"], name="idx_support_bettor_ts"),
            models.Index(fields=["status", "updated_at"], name="idx_support_status_ts"),
        ]

    def __str__(self):
        return f"{self.subject} ({self.status})"
