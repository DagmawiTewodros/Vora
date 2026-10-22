from django.conf import settings
from django.db import models


class Outlet(models.TextChoices):
    ROOM = "room", "Room"
    RESTAURANT = "restaurant", "Restaurant"
    BAR = "bar", "Bar"
    CAFE = "cafe", "Café"
    ROOM_SERVICE = "room_service", "Room service"
    MINIBAR = "minibar", "Minibar"
    LAUNDRY = "laundry", "Laundry"
    OTHER = "other", "Other"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card (POS terminal)"
    TELEBIRR = "telebirr", "Telebirr"
    CBE_BIRR = "cbe_birr", "CBE Birr"
    BANK_TRANSFER = "bank_transfer", "Bank transfer"
    CITY_LEDGER = "city_ledger", "Company account (city ledger)"


class CashierShift(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shifts")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_float = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    counted_cash_etb = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    counted_cash_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(fields=["cashier"], condition=models.Q(status="open"), name="one_open_shift_per_cashier"),
        ]

    def __str__(self):
        return f"Shift #{self.pk} {self.cashier} {self.opened_at:%Y-%m-%d %H:%M}"


class Folio(models.Model):
    """A guest bill. Every outlet posts charges here; when closed it becomes the invoice."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        VOID = "void", "Void"

    number = models.CharField(max_length=20, unique=True)
    reservation = models.ForeignKey(
        "reservations.Reservation", null=True, blank=True, on_delete=models.PROTECT, related_name="folios"
    )
    guest = models.ForeignKey("guests.Guest", null=True, blank=True, on_delete=models.PROTECT, related_name="folios")
    name = models.CharField(max_length=120, help_text="Who the bill is for.")
    is_primary = models.BooleanField(default=True)
    display_currency = models.CharField(max_length=3, choices=[("ETB", "ETB"), ("USD", "USD")], default="ETB")
    bill_to_name = models.CharField(max_length=120, blank=True, help_text="Company name on the invoice.")
    bill_to_tin = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    invoice_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    fiscal_receipt_number = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return f"Folio {self.number} ({self.name})"


class Charge(models.Model):
    folio = models.ForeignKey(Folio, on_delete=models.PROTECT, related_name="charges")
    outlet = models.CharField(max_length=20, choices=Outlet.choices)
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    business_date = models.DateField()
    room_night = models.DateField(null=True, blank=True, help_text="Set for room charges; one per night.")
    original_currency = models.CharField(max_length=3, default="ETB")
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    source_type = models.CharField(max_length=30, blank=True)
    source_id = models.CharField(max_length=40, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    posted_at = models.DateTimeField(auto_now_add=True)
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["posted_at", "id"]
        indexes = [models.Index(fields=["business_date", "outlet"]), models.Index(fields=["source_type", "source_id"])]

    def __str__(self):
        return f"{self.description} {self.total}"


class Payment(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        PAYMENT = "payment", "Payment"
        REFUND = "refund", "Refund"

    folio = models.ForeignKey(Folio, on_delete=models.PROTECT, related_name="payments")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PAYMENT)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    currency = models.CharField(max_length=3, choices=[("ETB", "ETB"), ("USD", "USD")], default="ETB")
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="In the payment currency; negative for refunds.")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    amount_etb = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=80, blank=True, help_text="Card slip, Telebirr or bank transaction id.")
    shift = models.ForeignKey(CashierShift, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    business_date = models.DateField()
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at", "id"]

    def __str__(self):
        return f"{self.get_method_display()} {self.amount} {self.currency}"


class DocumentSequence(models.Model):
    """Gap-free counters for folio and invoice numbers (required for tax audits)."""

    key = models.CharField(max_length=30, unique=True)
    last_number = models.PositiveIntegerField(default=0)
