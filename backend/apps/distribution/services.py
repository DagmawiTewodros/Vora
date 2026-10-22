"""Channel manager and booking engine.

Availability is computed from the same reservation table the front desk uses,
so an OTA booking, a walk-in and a website booking can never take the same
last room. Pushing to a real channel manager needs that provider's API; this
module builds the payload and records it, and `send` is the single place to
add the HTTP call once the hotel picks a provider.
"""

import datetime
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.money import money
from apps.guests.models import Guest
from apps.reservations import services as booking
from apps.reservations.models import Reservation
from apps.rooms.models import RoomType

from .models import ChannelSyncLog

logger = logging.getLogger("vora.channels")


def availability_payload(channel, start, days=30):
    end = start + datetime.timedelta(days=days)
    grid = booking.availability(start, end)
    rooms = []
    for room_type in RoomType.objects.all():
        nights = []
        for night, left in grid[room_type.pk].items():
            q = booking.quote(room_type, night, night + datetime.timedelta(days=1), "USD", public_only=True)
            price = money(Decimal(q["total"]) * (1 + channel.rate_markup_pct / 100))
            nights.append({
                "date": night.isoformat(),
                "available": 0 if channel.stop_sell else max(left - channel.inventory_buffer, 0),
                "rate_usd": str(price),
            })
        rooms.append({"room_type": room_type.code, "name": room_type.name, "nights": nights})
    return {"channel": channel.code, "generated_at": timezone.now().isoformat(), "rooms": rooms}


def send(channel, payload):
    """Deliver an availability update to the channel. Replace with the provider's API call."""
    logger.info("Availability for %s ready (%d room types); no provider API configured.", channel.code, len(payload["rooms"]))
    return True, "Prepared (no provider API configured)"


def push_availability(channel, start=None, days=30):
    payload = availability_payload(channel, start or timezone.localdate(), days)
    ok, message = send(channel, payload)
    channel.last_push_at = timezone.now()
    channel.save(update_fields=["last_push_at"])
    ChannelSyncLog.objects.create(channel=channel, direction=ChannelSyncLog.Direction.PUSH, ok=ok, message=message)
    return payload


def _parse_date(value, name):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({name: "Use the YYYY-MM-DD format."})


@transaction.atomic
def receive_booking(channel, data):
    """Create or cancel a reservation sent by an OTA. Idempotent on the OTA reference."""
    reference = str(data.get("reference") or "").strip()
    if not reference:
        raise ValidationError({"reference": "Missing OTA booking reference."})
    existing = Reservation.objects.filter(channel=channel.name, external_reference=reference).first()

    if data.get("status") == "cancelled":
        if existing and existing.status in (Reservation.Status.TENTATIVE, Reservation.Status.CONFIRMED):
            booking.cancel_reservation(existing, reason=f"Cancelled on {channel.name}")
        ChannelSyncLog.objects.create(channel=channel, direction=ChannelSyncLog.Direction.CANCEL, message=reference, payload=data)
        return existing
    if existing:
        return existing

    room_type = RoomType.objects.filter(code=data.get("room_type")).first()
    if room_type is None:
        raise ValidationError({"room_type": "Unknown room type code."})
    guest_data = data.get("guest") or {}
    if not guest_data.get("first_name"):
        raise ValidationError({"guest": "Guest first name is required."})
    guest = Guest.objects.create(
        first_name=guest_data.get("first_name", ""), last_name=guest_data.get("last_name", ""),
        email=guest_data.get("email", ""), phone=guest_data.get("phone", ""),
        nationality=guest_data.get("nationality", ""),
    )
    reservation = booking.create_reservation(
        guest=guest, room_type=room_type,
        check_in=_parse_date(data.get("check_in"), "check_in"),
        check_out=_parse_date(data.get("check_out"), "check_out"),
        adults=int(data.get("adults", 1)), children=int(data.get("children", 0)),
        source=Reservation.Source.OTA, channel=channel.name, external_reference=reference,
        currency=data.get("currency", "USD"),
        nightly_rate=Decimal(str(data["nightly_rate"])) if data.get("nightly_rate") is not None else None,
        special_requests=data.get("special_requests", ""),
    )
    ChannelSyncLog.objects.create(channel=channel, direction=ChannelSyncLog.Direction.BOOKING, message=reservation.code, payload=data)
    return reservation
