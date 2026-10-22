from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.billing import services as billing
from apps.billing.models import Outlet
from apps.core.money import money
from apps.reservations.models import Reservation

from .models import LaundryLine, LaundryPrice, LaundryTicket

FLOW = [LaundryTicket.Status.RECEIVED, LaundryTicket.Status.IN_PROCESS, LaundryTicket.Status.READY, LaundryTicket.Status.DELIVERED]


@transaction.atomic
def create_ticket(*, reservation, lines, express=False, notes="", user=None):
    if reservation.status != Reservation.Status.CHECKED_IN:
        raise ValidationError("Laundry can only be taken from in-house guests.")
    if not lines:
        raise ValidationError({"lines": "Add at least one item."})
    year = timezone.localdate().year
    ticket = LaundryTicket.objects.create(
        number=f"L{year}-{billing.next_number(f'laundry-{year}'):05d}",
        reservation=reservation, express=express, notes=notes, received_by=user,
    )
    for line in lines:
        price = line["price"] if isinstance(line["price"], LaundryPrice) else LaundryPrice.objects.get(pk=line["price"])
        if not price.is_active:
            raise ValidationError(f"{price} is no longer offered.")
        LaundryLine.objects.create(
            ticket=ticket, price=price, description=str(price), quantity=line.get("quantity", 1), unit_price=price.price
        )
    return ticket


def post_ticket(ticket, user=None):
    if ticket.posted:
        return
    folio = billing.primary_folio(ticket.reservation)
    for line in ticket.lines.all():
        unit = line.unit_price
        description = f"Laundry {ticket.number}: {line.description}"
        if ticket.express:
            unit = money(unit * (1 + ticket.express_surcharge_rate))
            description += " (express)"
        billing.post_charge(
            folio, outlet=Outlet.LAUNDRY, description=description, unit_price=unit, quantity=line.quantity,
            user=user, source_type="laundry_ticket", source_id=ticket.pk,
        )
    ticket.posted = True


@transaction.atomic
def advance(ticket, user=None):
    ticket = LaundryTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status not in FLOW[:-1]:
        raise ValidationError(f"A {ticket.get_status_display().lower()} ticket cannot move on.")
    ticket.status = FLOW[FLOW.index(ticket.status) + 1]
    if ticket.status == LaundryTicket.Status.DELIVERED:
        ticket.delivered_at = timezone.now()
        post_ticket(ticket, user)
    ticket.save()
    return ticket


@transaction.atomic
def cancel(ticket, user=None):
    ticket = LaundryTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.posted or ticket.status == LaundryTicket.Status.DELIVERED:
        raise ValidationError("Delivered tickets are already billed; void the folio charge instead.")
    ticket.status = LaundryTicket.Status.CANCELLED
    ticket.save()
    return ticket
