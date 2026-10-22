from django.conf import settings
from django.db import models


class NightAudit(models.Model):
    """One run of the end-of-day close: room charges posted and the day's figures frozen."""

    business_date = models.DateField(unique=True)
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    run_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(default=dict)

    class Meta:
        ordering = ["-business_date"]

    def __str__(self):
        return f"Night audit {self.business_date}"
