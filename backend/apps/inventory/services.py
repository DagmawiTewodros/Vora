from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import InventoryItem, PurchaseOrder, RecipeLine, StockMovement


@transaction.atomic
def move_stock(item, change, reason, *, reference="", note="", user=None):
    item = InventoryItem.objects.select_for_update().get(pk=item.pk)
    item.stock = item.stock + Decimal(change)
    item.save(update_fields=["stock"])
    return StockMovement.objects.create(
        item=item, change=change, reason=reason, reference=reference, note=note, stock_after=item.stock, user=user
    )


def deduct_for_order(order):
    """Take recipe quantities out of stock when a POS order is settled."""
    for line in order.items.filter(is_void=False):
        for recipe in RecipeLine.objects.filter(menu_item_id=line.menu_item_id).select_related("inventory_item"):
            move_stock(
                recipe.inventory_item, -(recipe.quantity * line.quantity), StockMovement.Reason.SALE,
                reference=order.number, note=line.name,
            )


@transaction.atomic
def count_stock(item, counted, *, user=None, note=""):
    item = InventoryItem.objects.select_for_update().get(pk=item.pk)
    difference = Decimal(counted) - item.stock
    if difference == 0:
        return None
    return move_stock(item, difference, StockMovement.Reason.ADJUSTMENT, note=note or "Stock count", user=user)


@transaction.atomic
def receive_purchase_order(po, *, received=None, user=None):
    """Book a delivery into stock. `received` maps line id to the quantity that actually arrived."""
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status not in (PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.ORDERED):
        raise ValidationError(f"A {po.get_status_display().lower()} purchase order cannot be received.")
    received = {int(k): v for k, v in (received or {}).items()}
    for line in po.lines.select_related("item"):
        qty = Decimal(received.get(line.pk, line.quantity))
        line.received_quantity = qty
        line.save(update_fields=["received_quantity"])
        if qty:
            move_stock(line.item, qty, StockMovement.Reason.PURCHASE, reference=po.number, user=user)
            line.item.refresh_from_db()
            line.item.unit_cost = line.unit_cost
            line.item.save(update_fields=["unit_cost"])
    po.status = PurchaseOrder.Status.RECEIVED
    po.received_at = timezone.now()
    po.save()
    return po
