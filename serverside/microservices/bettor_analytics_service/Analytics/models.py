from django.db import models


class AnalyticsDashboardLink(models.Model):
    class Meta:
        managed = False
        verbose_name = "Bettor Analytics Dashboard"
        verbose_name_plural = "Bettor Analytics Dashboard"
        app_label = "Analytics"

    def __str__(self):
        return "Bettor Analytics Dashboard"
