from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    FRONT_DESK = "front_desk", "Front desk"
    CASHIER = "cashier", "Cashier"
    HOUSEKEEPING = "housekeeping", "Housekeeping"
    WAITER = "waiter", "Waiter"
    LAUNDRY = "laundry", "Laundry"
    STORE_KEEPER = "store_keeper", "Store keeper"
    REVENUE = "revenue", "Revenue manager"
    SALES = "sales", "Sales"


class Staff(AbstractUser):
    """A hotel employee. Managers log in with a password, till staff with a PIN."""

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FRONT_DESK)
    phone = models.CharField(max_length=30, blank=True)
    preferred_language = models.CharField(max_length=2, choices=settings.LANGUAGES, default="en")
    pin_hash = models.CharField(max_length=128, blank=True)

    def set_pin(self, pin):
        self.pin_hash = make_password(pin) if pin else ""

    def check_pin(self, pin):
        return bool(self.pin_hash) and check_password(pin, self.pin_hash)

    @property
    def is_manager(self):
        return self.is_superuser or self.role in (Role.ADMIN, Role.MANAGER)

    def __str__(self):
        return self.get_full_name() or self.username


class HotelSettings(models.Model):
    """Single row of hotel-wide configuration edited by finance."""

    name = models.CharField(max_length=120, default="Vora Addis Hotel")
    address = models.CharField(max_length=255, default="Jomo Kenyatta Street, Kirkos, Addis Ababa, Ethiopia")
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    tin = models.CharField("TIN", max_length=20, blank=True)
    vat_registration_no = models.CharField(max_length=40, blank=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.15"))
    service_charge_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.10"))
    vat_on_service_charge = models.BooleanField(
        default=True, help_text="Charge VAT on the service charge as well as the base price."
    )
    prices_include_tax = models.BooleanField(
        default=False, help_text="Room rates and menu prices already include service charge and VAT."
    )
    show_ethiopian_date = models.BooleanField(default=True)
    invoice_prefix = models.CharField(max_length=10, default="VA")
    business_date = models.DateField(
        null=True, blank=True, help_text="Hotel trading day; advanced by the night audit."
    )
    check_in_time = models.TimeField(default="14:00")
    check_out_time = models.TimeField(default="12:00")

    class Meta:
        verbose_name_plural = "hotel settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def current_business_date(cls):
        from django.utils import timezone

        return cls.load().business_date or timezone.localdate()

    def __str__(self):
        return self.name


class ExchangeRate(models.Model):
    """Daily USD to ETB rate entered by finance."""

    date = models.DateField(unique=True)
    usd_to_etb = models.DecimalField(max_digits=10, decimal_places=4)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    @classmethod
    def rate_for(cls, day):
        rate = cls.objects.filter(date__lte=day).order_by("-date").first()
        return rate.usd_to_etb if rate else None

    def __str__(self):
        return f"{self.date}: 1 USD = {self.usd_to_etb} ETB"


class AuditLog(models.Model):
    """Who changed what, when, with before and after values."""

    class Action(models.TextChoices):
        CREATE = "create"
        UPDATE = "update"
        DELETE = "delete"
        ACTION = "action"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=10, choices=Action.choices)
    model = models.CharField(max_length=80)
    object_id = models.CharField(max_length=40)
    description = models.CharField(max_length=255, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.user} {self.action} {self.model}#{self.object_id}"
