"""POS rules: orders, kitchen tickets, posting to a room or settling at the till."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.billing import services as billing
from apps.billing.models import Outlet as ChargeOutlet
from apps.core.models import HotelSettings
from apps.reservations.models import Reservation

from .models import MenuItem, Order, OrderItem


def _number():
    year = timezone.localdate().year
    return f"P{year}-{billing.next_number(f'pos-{year}'):06d}"


@transaction.atomic
def create_order(*, outlet, waiter, table="", covers=1, items=(), notes="", client_uuid=None):
    if client_uuid:
        existing = Order.objects.filter(client_uuid=client_uuid).first()
        if existing:
            return existing
    order = Order.objects.create(
        number=_number(), outlet=outlet, waiter=waiter, table=table, covers=covers, notes=notes,
        client_uuid=client_uuid, business_date=HotelSettings.current_business_date(),
    )
    add_items(order, items)
    return order


def _require_open(order):
    if order.status != Order.Status.OPEN:
        raise ValidationError(f"Order {order.number} is {order.status}.")


@transaction.atomic
def add_items(order, items):
    _require_open(order)
    created = []
    for item in items:
        menu_item = item["menu_item"]
        if not isinstance(menu_item, MenuItem):
            menu_item = MenuItem.objects.get(pk=menu_item)
        if not menu_item.is_active:
            raise ValidationError(f"{menu_item.name} is not on the menu right now.")
        if not menu_item.outlets.filter(pk=order.outlet_id).exists():
            raise ValidationError(f"{menu_item.name} is not sold at {order.outlet.name}.")
        quantity = int(item.get("quantity", 1))
        if quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        created.append(OrderItem.objects.create(
            order=order, menu_item=menu_item, name=menu_item.name, quantity=quantity,
            unit_price=menu_item.price, notes=item.get("notes", ""),
            kitchen_status=OrderItem.KitchenStatus.NEW,
        ))
    return created


@transaction.atomic
def send_to_kitchen(order):
    _require_open(order)
    now = timezone.now()
    items = order.items.filter(kitchen_status=OrderItem.KitchenStatus.NEW, is_void=False)
    sent = []
    for item in items.select_related("menu_item"):
        item.kitchen_status = (
            OrderItem.KitchenStatus.SENT if item.menu_item.goes_to_kitchen and order.outlet.has_kitchen
            else OrderItem.KitchenStatus.SERVED
        )
        item.sent_at = now
        item.save()
        sent.append(item)
    return sent


@transaction.atomic
def void_item(item, reason, user=None):
    _require_open(item.order)
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    item.is_void = True
    item.notes = f"VOID: {reason}"[:120]
    item.save()
    return item


def _outlet_code(order):
    kind = order.outlet.kind
    return kind if kind in ChargeOutlet.values else ChargeOutlet.OTHER


def _post_items(order, folio, user):
    items = list(order.items.filter(is_void=False))
    if not items:
        raise ValidationError("The order has no items.")
    for item in items:
        billing.post_charge(
            folio, outlet=_outlet_code(order), description=f"{order.outlet.name}: {item.name}",
            unit_price=item.unit_price, quantity=item.quantity, user=user,
            source_type="pos_order", source_id=order.pk,
        )


def in_house_reservation(room_number):
    reservation = (
        Reservation.objects.select_related("room", "guest")
        .filter(room__number=room_number, status=Reservation.Status.CHECKED_IN)
        .first()
    )
    if reservation is None:
        raise ValidationError({"room": f"No guest is checked in to room {room_number}."})
    return reservation


@transaction.atomic
def post_to_room(order, room_number, *, user=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require_open(order)
    reservation = in_house_reservation(room_number)
    folio = billing.primary_folio(reservation)
    _post_items(order, folio, user)
    _finish(order, Order.Settlement.ROOM, folio)
    _deduct_stock(order)
    return order


@transaction.atomic
def settle_direct(order, *, payments, user=None, customer_name="", bill_to_name="", bill_to_tin=""):
    """Pay at the outlet: a walk-in folio is opened, paid and closed into an invoice."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require_open(order)
    folio = billing.open_folio(name=customer_name or f"{order.outlet.name} {order.table}".strip(), user=user)
    folio.bill_to_name, folio.bill_to_tin = bill_to_name, bill_to_tin
    folio.save()
    _post_items(order, folio, user)
    if not payments:
        raise ValidationError({"payments": "Enter at least one payment."})
    for payment in payments:
        billing.take_payment(folio, user=user, **payment)
    balance = billing.folio_balance(folio)
    if balance > 0:
        raise ValidationError(f"Payment is short by {balance} ETB.")
    if balance < 0:
        # Change given back in cash.
        billing.take_payment(folio, method="cash", amount=balance, user=user, kind="refund")
    billing.close_folio(folio, user=user)
    _finish(order, Order.Settlement.DIRECT, folio)
    _deduct_stock(order)
    return order


@transaction.atomic
def settle_complimentary(order, *, reason, user=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require_open(order)
    if not reason:
        raise ValidationError({"reason": "A reason is required for complimentary orders."})
    order.notes = f"Complimentary: {reason}"[:255]
    _finish(order, Order.Settlement.COMPLIMENTARY, None)
    _deduct_stock(order)
    return order


@transaction.atomic
def void_order(order, *, reason, user=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require_open(order)
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    order.status = Order.Status.VOID
    order.void_reason = reason
    order.save()
    return order


def _finish(order, settlement, folio):
    send_to_kitchen(order)
    order.status = Order.Status.SETTLED
    order.settlement = settlement
    order.folio = folio
    order.settled_at = timezone.now()
    order.save()


def _deduct_stock(order):
    from apps.inventory.services import deduct_for_order

    deduct_for_order(order)
