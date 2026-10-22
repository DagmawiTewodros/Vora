from django.contrib import admin

from .models import InventoryItem, PurchaseOrder, PurchaseOrderLine, RecipeLine, StockMovement, Supplier


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "supplier", "status", "expected_date", "created_at"]
    inlines = [PurchaseOrderLineInline]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "location", "stock", "unit", "reorder_level"]
    list_filter = ["location"]


admin.site.register(Supplier)
admin.site.register(RecipeLine)
admin.site.register(StockMovement)
