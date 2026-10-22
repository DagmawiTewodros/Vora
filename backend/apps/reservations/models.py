import secrets

from django.conf import settings
from django.db import models


def _reservation_code():
    return "R" + secrets.token_hex(3).upper()


class Group(models.Model):
    """A group or corporate block (conference delegations from ECA, tours...)."""

    name = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Reservation(models.Model):
    class Status(models.TextChoices):
        TENTATIVE = "tentative", "Tentative"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked in"
        CHECKED_OUT = "checked_out", "Checked out"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"

    class Source(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"
        OTA = "ota", "Online travel agency"
        DIRECT = "direct", "Hotel website"
        CORPORATE = "corporate", "Corporate"

    ACTIVE_STATUSES = (Status.TENTATIVE, Status.CONFIRMED, Status.CHECKED_IN)

    code = models.CharField(max_length=12, unique=True, default=_reservation_code)
    guest = models.ForeignKey("guests.Guest", on_delete=models.PROTECT, related_name="reservations")
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations")
    room_type = models.ForeignKey("rooms.RoomType", on_delete=models.PROTECT, related_name="reservations")
    room = models.ForeignKey("rooms.Room", null=True, blank=True, on_delete=models.PROTECT, related_name="reservations")
    rate_plan = models.ForeignKey("rooms.RatePlan", null=True, blank=True, on_delete=models.SET_NULL)
    check_in = models.DateField()
    check_out = models.DateField()
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.WALK_IN)
    channel = models.CharField(max_length=40, blank=True, help_text="OTA name, e.g. Expedia.")
    external_reference = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    currency = models.CharField(max_length=3, choices=[("ETB", "ETB"), ("USD", "USD")], default="ETB")
    nightly_rate = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Agreed price per night in the reservation currency."
    )
    breakfast_included = models.BooleanField(default=True)
    deposit_required = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    special_requests = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["check_in", "code"]
        indexes = [
            models.Index(fields=["status", "check_in"]),
            models.Index(fields=["room_type", "check_in", "check_out"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(check_out__gt=models.F("check_in")), name="check_out_after_check_in"),
        ]

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def __str__(self):
        return f"{self.code} {self.guest} {self.check_in}→{self.check_out}"


class Stay(models.Model):
    """What actually happened: real check-in/out times and the staff involved."""

    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name="stay")
    room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="stays")
    checked_in_at = models.DateTimeField()
    checked_in_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    key_cards_issued = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"Stay {self.reservation.code} in {self.room.number}"


class RoomMove(models.Model):
    stay = models.ForeignKey(Stay, on_delete=models.CASCADE, related_name="moves")
    from_room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="+")
    to_room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="+")
    reason = models.CharField(max_length=255, blank=True)
    moved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    moved_at = models.DateTimeField(auto_now_add=True)
