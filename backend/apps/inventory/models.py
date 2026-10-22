from django.conf import settings
from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    tin = models.CharField("TIN", max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    class Location(models.TextChoices):
        KITCHEN = "kitchen", "Kitchen"
        BAR = "bar", "Bar"
        MINIBAR = "minibar", "Minibar"
        AMENITIES = "amenities", "Guest amenities"
        HOUSEKEEPING = "housekeeping", "Housekeeping"
        STORE = "store", "Main store"

    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=30, unique=True)
    unit = models.CharField(max_length=20, help_text="kg, litre, bottle, piece...")
    location = models.CharField(max_length=15, choices=Location.choices, default=Location.STORE)
    stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    preferred_supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location", "name"]

    @property
    def needs_reorder(self):
        return self.stock <= self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.unit})"


class RecipeLine(models.Model):
    """How much stock one portion of a menu item uses."""

    menu_item = models.ForeignKey("pos.MenuItem", on_delete=models.CASCADE, related_name="recipe")
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="recipe_lines")
    quantity = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu_item", "inventory_item"], name="unique_recipe_line")]


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Purchase received"
        SALE = "sale", "Sold (POS)"
        ISSUE = "issue", "Issued to department"
        WASTE = "waste", "Waste / spoilage"
        ADJUSTMENT = "adjustment", "Stock count adjustment"

    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    change = models.DecimalField(max_digits=12, decimal_places=3, help_text="Positive adds stock, negative removes it.")
    reason = models.CharField(max_length=12, choices=Reason.choices)
    reference = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=255, blank=True)
    stock_after = models.DecimalField(max_digits=12, decimal_places=3)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ORDERED = "ordered", "Ordered"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=20, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PO {self.number}"


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
