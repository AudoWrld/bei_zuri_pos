from django.db import models


class SyncLog(models.Model):
    SYNC_TYPES = [
        ("initial", "Initial Sync"),
        ("pull", "Pull Updates"),
        ("push", "Push Data"),
    ]

    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    status = models.CharField(max_length=20)
    records_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.sync_type} - {self.status} ({self.started_at})"
