from decimal import Decimal

from django.conf import settings
from django.db import models


class LaundryPrice(models.Model):
    class Service(models.TextChoices):
        WASH = "wash", "Wash & iron"
        DRY_CLEAN = "dry_clean", "Dry cleaning"
        PRESS = "press", "Pressing only"

    item = models.CharField(max_length=60, help_text="e.g. Shirt, Trousers, Suit (2 pc)")
    item_am = models.CharField("Item (Amharic)", max_length=60, blank=True)
    service = models.CharField(max_length=10, choices=Service.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item", "service"]
        constraints = [models.UniqueConstraint(fields=["item", "service"], name="unique_laundry_price")]

    def __str__(self):
        return f"{self.item} – {self.get_service_display()}"


class LaundryTicket(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        IN_PROCESS = "in_process", "In process"
        READY = "ready", "Ready"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=20, unique=True)
    reservation = models.ForeignKey("reservations.Reservation", on_delete=models.PROTECT, related_name="laundry_tickets")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    express = models.BooleanField(default=False)
    express_surcharge_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.50"))
    notes = models.CharField(max_length=255, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    received_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    posted = models.BooleanField(default=False, help_text="Charges posted to the guest folio.")

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"Laundry {self.number}"


class LaundryLine(models.Model):
    ticket = models.ForeignKey(LaundryTicket, on_delete=models.CASCADE, related_name="lines")
    price = models.ForeignKey(LaundryPrice, on_delete=models.PROTECT)
    description = models.CharField(max_length=100)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.unit_price * self.quantity
