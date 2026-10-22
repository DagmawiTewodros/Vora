import secrets

from django.db import models


def _secret():
    return secrets.token_urlsafe(32)


class ChannelConnection(models.Model):
    """An OTA or channel-manager link (Expedia, Booking.com...).

    Inventory and rates are pushed out; reservations come in through the
    webhook, authenticated with the per-channel secret.
    """

    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=30, unique=True)
    is_active = models.BooleanField(default=False)
    stop_sell = models.BooleanField(default=False, help_text="Close all inventory on this channel (e.g. on go-live day).")
    rate_markup_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Added to public rates.")
    inventory_buffer = models.PositiveSmallIntegerField(default=0, help_text="Rooms per type held back from this channel.")
    webhook_secret = models.CharField(max_length=64, default=_secret)
    endpoint_url = models.URLField(blank=True, help_text="Where availability updates are sent.")
    last_push_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class ChannelSyncLog(models.Model):
    class Direction(models.TextChoices):
        PUSH = "push", "Availability pushed"
        BOOKING = "booking", "Booking received"
        CANCEL = "cancel", "Cancellation received"

    channel = models.ForeignKey(ChannelConnection, on_delete=models.CASCADE, related_name="logs")
    direction = models.CharField(max_length=10, choices=Direction.choices)
    ok = models.BooleanField(default=True)
    message = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
