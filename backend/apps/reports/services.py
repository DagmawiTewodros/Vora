"""Owner reports: occupancy, ADR, RevPAR, outlet revenue, and the night audit."""

import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from rest_framework.exceptions import ValidationError

from apps.billing.models import CashierShift, Charge, Folio, Outlet, Payment
from apps.billing.services import post_room_charges
from apps.core.models import HotelSettings
from apps.core.money import money
from apps.housekeeping.services import create_stayover_tasks
from apps.pos.models import BreakfastLog
from apps.reservations.models import Reservation
from apps.rooms.models import Room

from .models import NightAudit

ZERO = Decimal("0.00")


def _pct(part, whole):
    return round(float(part) * 100 / float(whole), 1) if whole else 0.0


def rooms_available(day):
    # Out-of-order rooms are not sellable; this uses the current status, which is
    # exact for the night audit and close enough for past days.
    return Room.objects.filter(is_active=True).exclude(status=Room.Status.OUT_OF_ORDER).count()


def day_report(day):
    room_charges = Charge.objects.filter(outlet=Outlet.ROOM, room_night=day, is_void=False)
    rooms_sold = room_charges.values("folio__reservation").distinct().count()
    room_revenue_net = room_charges.aggregate(t=Sum("net_amount"))["t"] or ZERO
    available = rooms_available(day)

    outlet_rows = (
        Charge.objects.filter(business_date=day, is_void=False)
        .values("outlet")
        .annotate(net=Sum("net_amount"), service=Sum("service_charge"), vat=Sum("vat"), total=Sum("total"), count=Count("id"))
        .order_by("outlet")
    )
    labels = dict(Outlet.choices)
    by_outlet = [
        {"outlet": r["outlet"], "label": labels.get(r["outlet"], r["outlet"]), "net": r["net"], "service_charge": r["service"],
         "vat": r["vat"], "total": r["total"], "count": r["count"]}
        for r in outlet_rows
    ]
    payments = (
        Payment.objects.filter(business_date=day)
        .values("method", "currency")
        .annotate(amount=Sum("amount"), amount_etb=Sum("amount_etb"))
        .order_by("method")
    )
    arrivals = Reservation.objects.filter(stay__checked_in_at__date=day).count()
    departures = Reservation.objects.filter(stay__checked_out_at__date=day).count()
    guests = Reservation.objects.filter(
        status__in=[Reservation.Status.CHECKED_IN, Reservation.Status.CHECKED_OUT], check_in__lte=day, check_out__gt=day
    ).aggregate(adults=Sum("adults"), children=Sum("children"))

    return {
        "date": day,
        "rooms_available": available,
        "rooms_sold": rooms_sold,
        "occupancy_pct": _pct(rooms_sold, available),
        "room_revenue": room_revenue_net,
        "adr": money(room_revenue_net / rooms_sold) if rooms_sold else ZERO,
        "revpar": money(room_revenue_net / available) if available else ZERO,
        "revenue_by_outlet": by_outlet,
        "total_revenue_net": sum((r["net"] for r in by_outlet), start=ZERO),
        "total_vat": sum((r["vat"] for r in by_outlet), start=ZERO),
        "total_service_charge": sum((r["service_charge"] for r in by_outlet), start=ZERO),
        "payments": list(payments),
        "arrivals": arrivals,
        "departures": departures,
        "guests_in_house": (guests["adults"] or 0) + (guests["children"] or 0),
    }


def range_report(start, end):
    if end < start:
        raise ValidationError("End date must be on or after the start date.")
    if (end - start).days > 366:
        raise ValidationError("Ask for at most one year at a time.")
    days = [day_report(start + datetime.timedelta(days=i)) for i in range((end - start).days + 1)]
    sold = sum(d["rooms_sold"] for d in days)
    available = sum(d["rooms_available"] for d in days)
    revenue = sum((d["room_revenue"] for d in days), start=ZERO)
    outlets = {}
    for d in days:
        for row in d["revenue_by_outlet"]:
            agg = outlets.setdefault(row["outlet"], {"outlet": row["outlet"], "label": row["label"], "net": ZERO, "total": ZERO})
            agg["net"] += row["net"]
            agg["total"] += row["total"]
    return {
        "start": start,
        "end": end,
        "days": days,
        "totals": {
            "rooms_sold": sold,
            "rooms_available": available,
            "occupancy_pct": _pct(sold, available),
            "room_revenue": revenue,
            "adr": money(revenue / sold) if sold else ZERO,
            "revpar": money(revenue / available) if available else ZERO,
            "revenue_by_outlet": list(outlets.values()),
            "total_revenue_net": sum((o["net"] for o in outlets.values()), start=ZERO),
        },
    }


def guest_register(day):
    """Printable list of in-house guests for police checks."""
    reservations = (
        Reservation.objects.select_related("guest", "room", "stay")
        .filter(status__in=[Reservation.Status.CHECKED_IN, Reservation.Status.CHECKED_OUT], check_in__lte=day, check_out__gt=day)
        .order_by("room__number")
    )
    return [
        {
            "room": r.room.number if r.room_id else "",
            "name": r.guest.full_name,
            "nationality": r.guest.nationality,
            "id_type": r.guest.get_id_type_display(),
            "id_number": r.guest.id_number,
            "visa_number": r.guest.visa_number,
            "visa_expiry": r.guest.visa_expiry,
            "phone": r.guest.phone,
            "check_in": r.check_in,
            "check_out": r.check_out,
            "adults": r.adults,
            "children": r.children,
        }
        for r in reservations
    ]


def breakfast_report(day):
    # Breakfast is served the morning after each night, so a guest is entitled
    # from the day after arrival up to and including the departure day.
    entitled = Reservation.objects.select_related("guest", "room").filter(
        status__in=[Reservation.Status.CHECKED_IN, Reservation.Status.CHECKED_OUT],
        breakfast_included=True, check_in__lt=day, check_out__gte=day,
    )
    taken = {b.reservation_id: b.covers for b in BreakfastLog.objects.filter(business_date=day)}
    rows = [
        {"reservation": r.pk, "room": r.room.number if r.room_id else "", "guest": r.guest.full_name,
         "guests": r.adults + r.children, "covers_taken": taken.get(r.pk, 0)}
        for r in entitled
    ]
    return {
        "date": day,
        "entitled_covers": sum(r["guests"] for r in rows),
        "covers_taken": sum(taken.values()),
        "rooms": rows,
    }


@transaction.atomic
def run_night_audit(user=None):
    """Close the business day: post room nights, flag no-shows, roll the date forward."""
    hotel = HotelSettings.objects.select_for_update().get_or_create(pk=1)[0]
    day = HotelSettings.current_business_date()
    if NightAudit.objects.filter(business_date=day).exists():
        raise ValidationError(f"The night audit for {day} has already run.")

    open_shifts = CashierShift.objects.filter(status=CashierShift.Status.OPEN).count()

    posted = 0
    for reservation in Reservation.objects.filter(status=Reservation.Status.CHECKED_IN).select_related("room", "room_type"):
        posted += len(post_room_charges(reservation, through=day, user=user))

    pending_arrivals = Reservation.objects.filter(
        status__in=[Reservation.Status.TENTATIVE, Reservation.Status.CONFIRMED], check_in__lte=day
    )
    no_show_codes = list(pending_arrivals.values_list("code", flat=True))
    overdue_departures = list(
        Reservation.objects.filter(status=Reservation.Status.CHECKED_IN, check_out__lte=day).values_list("code", flat=True)
    )

    report = day_report(day)
    summary = {
        "room_nights_posted": posted,
        "possible_no_shows": no_show_codes,
        "overdue_departures": overdue_departures,
        "open_cashier_shifts": open_shifts,
        "open_folios": Folio.objects.filter(status=Folio.Status.OPEN).count(),
        "report": report,
    }
    audit = NightAudit.objects.create(business_date=day, run_by=user, summary=_json(summary))

    hotel.business_date = day + datetime.timedelta(days=1)
    hotel.save()
    create_stayover_tasks()
    return audit


def _json(value):
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, (Decimal, datetime.date)):
        return str(value)
    return value
