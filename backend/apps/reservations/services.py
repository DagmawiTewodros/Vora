"""Booking rules: availability, the double-booking guard, check-in and check-out."""

import datetime
from collections import defaultdict

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core import audit
from apps.core.models import ExchangeRate, HotelSettings
from apps.rooms.models import RatePlan, Room, RoomType

from .models import Reservation, RoomMove, Stay


def nights_between(start, end):
    return [start + datetime.timedelta(days=i) for i in range((end - start).days)]


def _overlapping(start, end):
    return Reservation.objects.filter(
        status__in=Reservation.ACTIVE_STATUSES, check_in__lt=end, check_out__gt=start
    )


def availability(start, end, *, room_type=None, exclude=None):
    """Rooms left to sell per room type per night: {room_type_id: {night: count}}."""
    if end <= start:
        raise ValidationError("Check-out must be after check-in.")
    types = RoomType.objects.all() if room_type is None else RoomType.objects.filter(pk=getattr(room_type, "pk", room_type))
    rooms = defaultdict(int)
    for room in Room.objects.filter(is_active=True, room_type__in=types).exclude(status=Room.Status.OUT_OF_ORDER):
        rooms[room.room_type_id] += 1

    booked = defaultdict(lambda: defaultdict(int))
    reservations = _overlapping(start, end).filter(room_type__in=types)
    if exclude is not None:
        reservations = reservations.exclude(pk=exclude.pk)
    for res in reservations.only("room_type_id", "check_in", "check_out"):
        for night in nights_between(max(res.check_in, start), min(res.check_out, end)):
            booked[res.room_type_id][night] += 1

    nights = nights_between(start, end)
    return {
        rt.pk: {night: rooms[rt.pk] - booked[rt.pk][night] for night in nights}
        for rt in types
    }


def rooms_left(room_type, start, end, *, exclude=None):
    per_night = availability(start, end, room_type=room_type, exclude=exclude)[room_type.pk]
    return min(per_night.values()) if per_night else 0


def room_is_free(room, start, end, *, exclude=None):
    clash = _overlapping(start, end).filter(room=room)
    if exclude is not None:
        clash = clash.exclude(pk=exclude.pk)
    return not clash.exists()


def free_rooms(room_type, start, end, *, exclude=None):
    taken = _overlapping(start, end).exclude(room__isnull=True)
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    return (
        Room.objects.filter(room_type=room_type, is_active=True)
        .exclude(status=Room.Status.OUT_OF_ORDER)
        .exclude(pk__in=taken.values("room_id"))
    )


def quote(room_type, start, end, currency="ETB", rate_plan=None, *, public_only=False):
    """Price per night and total for a stay, using the best rate plan for each night."""
    nights = []
    for night in nights_between(start, end):
        plan = rate_plan if rate_plan and rate_plan.covers(night) else RatePlan.for_night(room_type, night, public_only=public_only)
        if plan:
            price = plan.price_usd if currency == "USD" else plan.price_etb
        else:
            price = room_type.base_rate_usd if currency == "USD" else room_type.base_rate_etb
        nights.append({"night": night, "rate_plan": plan.pk if plan else None, "price": price})
    total = sum((n["price"] for n in nights), start=0)
    first_plan = RatePlan.objects.filter(pk=nights[0]["rate_plan"]).first() if nights and nights[0]["rate_plan"] else None
    return {"nights": nights, "total": total, "currency": currency, "rate_plan": first_plan}


def _validate_dates(check_in, check_out):
    if check_out <= check_in:
        raise ValidationError({"check_out": "Check-out must be after check-in."})


def _check_capacity(room_type, adults, children):
    if adults + children > room_type.capacity:
        raise ValidationError({"adults": f"{room_type.name} sleeps at most {room_type.capacity} guests."})


@transaction.atomic
def create_reservation(*, user=None, **data):
    room_type = RoomType.objects.select_for_update().get(pk=data["room_type"].pk)
    check_in, check_out = data["check_in"], data["check_out"]
    _validate_dates(check_in, check_out)
    _check_capacity(room_type, data.get("adults", 1), data.get("children", 0))

    if rooms_left(room_type, check_in, check_out) < 1:
        raise ValidationError(f"No {room_type.name} rooms are free for every night from {check_in} to {check_out}.")

    room = data.get("room")
    if room is not None:
        if room.room_type_id != room_type.pk:
            raise ValidationError({"room": f"Room {room.number} is not a {room_type.name}."})
        if not room_is_free(room, check_in, check_out):
            raise ValidationError({"room": f"Room {room.number} is already booked for those dates."})

    currency = data.get("currency", "ETB")
    if data.get("nightly_rate") is None:
        q = quote(room_type, check_in, check_out, currency, data.get("rate_plan"))
        data["nightly_rate"] = q["nights"][0]["price"]
        data.setdefault("rate_plan", q["rate_plan"])
    if data.get("rate_plan") is not None and "breakfast_included" not in data:
        data["breakfast_included"] = data["rate_plan"].breakfast_included

    data["room_type"] = room_type
    reservation = Reservation.objects.create(created_by=user, **data)

    from apps.billing.services import open_folio

    open_folio(reservation=reservation)
    return reservation


@transaction.atomic
def update_reservation(reservation, *, user=None, **changes):
    reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
    if reservation.status in (Reservation.Status.CHECKED_OUT, Reservation.Status.CANCELLED, Reservation.Status.NO_SHOW):
        raise ValidationError("Closed reservations cannot be changed.")
    if reservation.status == Reservation.Status.CHECKED_IN:
        locked = {"check_in", "room", "room_type"} & {k for k, v in changes.items() if v != getattr(reservation, k)}
        if locked:
            raise ValidationError(f"Use a room move or check-out to change {', '.join(sorted(locked))} for an in-house guest.")

    room_type = RoomType.objects.select_for_update().get(pk=changes.get("room_type", reservation.room_type).pk)
    check_in = changes.get("check_in", reservation.check_in)
    check_out = changes.get("check_out", reservation.check_out)
    room = changes.get("room", reservation.room)
    _validate_dates(check_in, check_out)
    _check_capacity(room_type, changes.get("adults", reservation.adults), changes.get("children", reservation.children))

    if rooms_left(room_type, check_in, check_out, exclude=reservation) < 1:
        raise ValidationError(f"No {room_type.name} rooms are free for every night from {check_in} to {check_out}.")
    if room is not None:
        if room.room_type_id != room_type.pk:
            raise ValidationError({"room": f"Room {room.number} is not a {room_type.name}."})
        if not room_is_free(room, check_in, check_out, exclude=reservation):
            raise ValidationError({"room": f"Room {room.number} is already booked for those dates."})

    for key, value in changes.items():
        setattr(reservation, key, value)
    reservation.save()
    return reservation


@transaction.atomic
def cancel_reservation(reservation, *, reason="", user=None, no_show=False):
    reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
    if reservation.status not in (Reservation.Status.TENTATIVE, Reservation.Status.CONFIRMED):
        raise ValidationError(f"A {reservation.get_status_display().lower()} reservation cannot be cancelled.")
    reservation.status = Reservation.Status.NO_SHOW if no_show else Reservation.Status.CANCELLED
    reservation.cancelled_at = timezone.now()
    reservation.cancellation_reason = reason
    reservation.save()
    audit.log("action", reservation, description=f"{'No-show' if no_show else 'Cancelled'}: {reason}", user=user)
    return reservation


def registration_problems(guest):
    problems = []
    if not guest.id_number:
        problems.append("ID or passport number is missing.")
    if not guest.nationality:
        problems.append("Nationality is missing.")
    if guest.is_foreign and guest.id_type != guest.IdType.PASSPORT:
        problems.append("Foreign guests must register with a passport.")
    return problems


@transaction.atomic
def check_in(reservation, *, room=None, user=None, force=False, key_cards=1):
    reservation = Reservation.objects.select_for_update().select_related("guest").get(pk=reservation.pk)
    today = HotelSettings.current_business_date()
    if reservation.status not in (Reservation.Status.TENTATIVE, Reservation.Status.CONFIRMED):
        raise ValidationError(f"Cannot check in a {reservation.get_status_display().lower()} reservation.")
    if reservation.check_in > today:
        raise ValidationError(f"This reservation starts on {reservation.check_in}; change the dates to check in early.")
    if reservation.check_out <= today:
        raise ValidationError("The reservation dates have passed; update the check-out date first.")

    problems = registration_problems(reservation.guest)
    if problems:
        raise ValidationError({"guest": problems})

    room = room or reservation.room
    if room is None:
        raise ValidationError({"room": "Assign a room before check-in."})
    room = Room.objects.select_for_update().get(pk=room.pk)
    if room.room_type_id != reservation.room_type_id:
        raise ValidationError({"room": f"Room {room.number} is not a {reservation.room_type.name}; change the room type first."})
    if room.status != Room.Status.VACANT:
        raise ValidationError({"room": f"Room {room.number} is {room.get_status_display().lower()}."})
    if room.housekeeping_status == Room.Housekeeping.DIRTY and not force:
        raise ValidationError({"room": f"Room {room.number} has not been cleaned yet."})
    if not room_is_free(room, today, reservation.check_out, exclude=reservation):
        raise ValidationError({"room": f"Room {room.number} is booked by another reservation during this stay."})

    # Early arrival: the stay now starts today.
    if reservation.check_in < today:
        reservation.check_in = today

    reservation.room = room
    reservation.status = Reservation.Status.CHECKED_IN
    reservation.save()
    room.status = Room.Status.OCCUPIED
    room.save()
    Stay.objects.create(
        reservation=reservation, room=room, checked_in_at=timezone.now(), checked_in_by=user, key_cards_issued=key_cards
    )
    if reservation.currency == "USD" and ExchangeRate.rate_for(today) is None:
        audit.log("action", reservation, description="Checked in a USD reservation with no exchange rate entered", user=user)
    return reservation


def _departure_date(reservation, today):
    # Early departure releases the remaining nights back to inventory.
    if today < reservation.check_out:
        return max(today, reservation.check_in + datetime.timedelta(days=1))
    return reservation.check_out


def post_final_room_charges(reservation, *, user=None):
    """Post every room night up to departure so the guest can see and pay the final bill."""
    from apps.billing.services import post_room_charges

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        if reservation.status != Reservation.Status.CHECKED_IN:
            raise ValidationError("Only in-house guests can be checked out.")
        departure = _departure_date(reservation, HotelSettings.current_business_date())
        return post_room_charges(reservation, through=departure - datetime.timedelta(days=1), user=user)


def check_out(reservation, *, user=None):
    from apps.billing.services import close_folio, folio_balance
    from apps.housekeeping.services import create_departure_task

    # Room nights are committed first: they are owed whether or not the bill is
    # settled now, and the cashier needs them on the folio to take payment.
    post_final_room_charges(reservation, user=user)

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        reservation.check_out = _departure_date(reservation, HotelSettings.current_business_date())

        folios = list(reservation.folios.filter(status="open"))
        unpaid = [(f, folio_balance(f)) for f in folios]
        unpaid = [(f, b) for f, b in unpaid if b != 0]
        if unpaid:
            detail = "; ".join(f"folio {f.number}: {b} ETB" for f, b in unpaid)
            raise ValidationError(f"Settle the bill before check-out ({detail}).")
        for folio in folios:
            close_folio(folio, user=user)

        reservation.status = Reservation.Status.CHECKED_OUT
        reservation.save()
        stay = reservation.stay
        stay.checked_out_at = timezone.now()
        stay.checked_out_by = user
        stay.save()
        room = Room.objects.select_for_update().get(pk=reservation.room_id)
        room.status = Room.Status.VACANT
        room.housekeeping_status = Room.Housekeeping.DIRTY
        room.save()
        create_departure_task(room)
        return reservation


@transaction.atomic
def move_room(reservation, to_room, *, reason="", user=None):
    reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
    if reservation.status != Reservation.Status.CHECKED_IN:
        raise ValidationError("Only in-house guests can change rooms.")
    to_room = Room.objects.select_for_update().get(pk=to_room.pk)
    if to_room.pk == reservation.room_id:
        raise ValidationError("The guest is already in that room.")
    if not to_room.is_ready:
        raise ValidationError({"room": f"Room {to_room.number} is not vacant and clean."})
    today = HotelSettings.current_business_date()
    if not room_is_free(to_room, today, reservation.check_out, exclude=reservation):
        raise ValidationError({"room": f"Room {to_room.number} is booked during the rest of this stay."})
    if to_room.room_type_id != reservation.room_type_id:
        if rooms_left(to_room.room_type, today, reservation.check_out) < 1:
            raise ValidationError(f"No {to_room.room_type.name} inventory left for the rest of this stay.")
        reservation.room_type = to_room.room_type

    from apps.housekeeping.services import create_departure_task

    old_room = Room.objects.select_for_update().get(pk=reservation.room_id)
    old_room.status = Room.Status.VACANT
    old_room.housekeeping_status = Room.Housekeeping.DIRTY
    old_room.save()
    create_departure_task(old_room)

    to_room.status = Room.Status.OCCUPIED
    to_room.save()
    reservation.room = to_room
    reservation.save()
    stay = reservation.stay
    RoomMove.objects.create(stay=stay, from_room=old_room, to_room=to_room, reason=reason, moved_by=user)
    stay.room = to_room
    stay.save()
    return reservation
