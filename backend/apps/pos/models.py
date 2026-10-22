from django.conf import settings
from django.db import models


class Outlet(models.Model):
    """A selling point: restaurant, bar, café, room service."""

    class Kind(models.TextChoices):
        RESTAURANT = "restaurant", "Restaurant"
        BAR = "bar", "Bar"
        CAFE = "cafe", "Café"
        ROOM_SERVICE = "room_service", "Room service"
        MINIBAR = "minibar", "Minibar"

    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    has_kitchen = models.BooleanField(default=True, help_text="Send food items to the kitchen screen/printer.")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class MenuCategory(models.Model):
    name = models.CharField(max_length=60)
    name_am = models.CharField("Name (Amharic)", max_length=60, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "menu categories"

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    outlets = models.ManyToManyField(Outlet, related_name="menu_items")
    category = models.ForeignKey(MenuCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    name = models.CharField(max_length=100)
    name_am = models.CharField("Name (Amharic)", max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="ETB per portion.")
    goes_to_kitchen = models.BooleanField(default=True)
    is_breakfast = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__sort_order", "name"]

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        SETTLED = "settled", "Settled"
        VOID = "void", "Void"

    class Settlement(models.TextChoices):
        ROOM = "room", "Posted to room"
        DIRECT = "direct", "Paid at outlet"
        COMPLIMENTARY = "complimentary", "Complimentary"

    number = models.CharField(max_length=20, unique=True)
    client_uuid = models.UUIDField(unique=True, null=True, blank=True, help_text="Set by offline tills for safe re-sync.")
    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name="orders")
    table = models.CharField(max_length=20, blank=True)
    covers = models.PositiveSmallIntegerField(default=1)
    waiter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="pos_orders")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    settlement = models.CharField(max_length=15, choices=Settlement.choices, blank=True)
    folio = models.ForeignKey("billing.Folio", null=True, blank=True, on_delete=models.PROTECT, related_name="orders")
    notes = models.CharField(max_length=255, blank=True)
    business_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.number}"


class OrderItem(models.Model):
    class KitchenStatus(models.TextChoices):
        NEW = "new", "Not sent"
        SENT = "sent", "Sent to kitchen"
        READY = "ready", "Ready"
        SERVED = "served", "Served"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=120, blank=True)
    kitchen_status = models.CharField(max_length=10, choices=KitchenStatus.choices, default=KitchenStatus.NEW)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_void = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class BreakfastLog(models.Model):
    """Breakfast taken by an in-house reservation on a given day."""

    reservation = models.ForeignKey("reservations.Reservation", on_delete=models.CASCADE, related_name="breakfasts")
    business_date = models.DateField()
    covers = models.PositiveSmallIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["reservation", "business_date"], name="one_breakfast_log_per_day")]
