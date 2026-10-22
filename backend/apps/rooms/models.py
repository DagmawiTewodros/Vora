from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class RoomType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=10, unique=True)
    capacity = models.PositiveSmallIntegerField(default=2)
    base_rate_etb = models.DecimalField(max_digits=12, decimal_places=2)
    base_rate_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    description = models.TextField(blank=True)
    amenities = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Room(models.Model):
    class Status(models.TextChoices):
        VACANT = "vacant", "Vacant"
        OCCUPIED = "occupied", "Occupied"
        OUT_OF_ORDER = "out_of_order", "Out of order"

    class Housekeeping(models.TextChoices):
        DIRTY = "dirty", "Dirty"
        CLEAN = "clean", "Clean"
        INSPECTED = "inspected", "Inspected"

    number = models.CharField(max_length=10, unique=True)
    floor = models.SmallIntegerField(default=1)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.VACANT)
    housekeeping_status = models.CharField(max_length=20, choices=Housekeeping.choices, default=Housekeeping.CLEAN)
    out_of_order_reason = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["floor", "number"]

    @property
    def is_ready(self):
        return self.status == self.Status.VACANT and self.housekeeping_status in (
            self.Housekeeping.CLEAN, self.Housekeeping.INSPECTED
        )

    def __str__(self):
        return f"{self.number} ({self.room_type.code})"


class RatePlan(models.Model):
    """A sellable price for a room type, optionally limited to a season."""

    name = models.CharField(max_length=80)
    code = models.CharField(max_length=20)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name="rate_plans")
    price_etb = models.DecimalField(max_digits=12, decimal_places=2)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    breakfast_included = models.BooleanField(default=True)
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True, help_text="Last night the rate applies (inclusive).")
    min_nights = models.PositiveSmallIntegerField(default=1)
    is_corporate = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True, help_text="Offered on the booking engine and OTAs.")
    is_active = models.BooleanField(default=True)
    priority = models.SmallIntegerField(default=0, help_text="Higher wins when several plans cover a night.")

    class Meta:
        ordering = ["room_type", "-priority", "name"]
        constraints = [models.UniqueConstraint(fields=["room_type", "code"], name="unique_rate_code_per_type")]

    def clean(self):
        if self.season_start and self.season_end and self.season_end < self.season_start:
            raise ValidationError("Season end must be on or after season start.")

    def covers(self, night):
        return (not self.season_start or self.season_start <= night) and (not self.season_end or night <= self.season_end)

    @classmethod
    def for_night(cls, room_type, night, *, public_only=False):
        qs = cls.objects.filter(room_type=room_type, is_active=True).filter(
            Q(season_start__isnull=True) | Q(season_start__lte=night),
            Q(season_end__isnull=True) | Q(season_end__gte=night),
        )
        if public_only:
            qs = qs.filter(is_public=True)
        return qs.order_by("-priority", "price_etb").first()

    def __str__(self):
        return f"{self.room_type.code} {self.name}"
