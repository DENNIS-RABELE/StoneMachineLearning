from django.db import models

class UnityGameConfig(models.Model):
    name = models.CharField(max_length=80, unique=True, default="default")
    build_url = models.URLField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "Unity game config"
        verbose_name_plural = "Unity game configs"

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"


class UnityGameplayDashboardLink(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        db_table = "unity_gameplay_dashboard_link"
        verbose_name = "Unity Gameplay Dashboard"
        verbose_name_plural = "Unity Gameplay Dashboard"
        app_label = "Gameplay"

    def __str__(self):
        return "Unity Gameplay Dashboard"


class GlobalGameplayState(models.Model):
    STATUS_RUNNING = "RUNNING"
    STATUS_STOPPED = "STOPPED"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_STOPPED, "Stopped"),
    ]

    key = models.CharField(max_length=32, unique=True, default="global")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_STOPPED)
    tick = models.PositiveIntegerField(default=0)
    max_ticks = models.PositiveIntegerField(default=120)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Global gameplay state"
        verbose_name_plural = "Global gameplay state"

    def __str__(self):
        return f"{self.status} ({self.tick}/{self.max_ticks})"