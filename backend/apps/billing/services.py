"""Folio rules: posting charges, taking payments, splitting bills and invoicing."""

import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core import audit
from apps.core.ethiopian import format_ethiopian
from apps.core.models import ExchangeRate, HotelSettings
from apps.core.money import money, tax_breakdown

from .fiscal import get_driver
from .models import CashierShift, Charge, DocumentSequence, Folio, Outlet, Payment, PaymentMethod

ZERO = Decimal("0.00")


def next_number(key):
    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(key=key)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return seq.last_number


@transaction.atomic
def open_folio(*, reservation=None, guest=None, name="", is_primary=True, user=None):
    guest = guest or (reservation.guest if reservation else None)
    year = timezone.localdate().year
    number = f"F{year}-{next_number(f'folio-{year}'):05d}"
    return Folio.objects.create(
        number=number,
        reservation=reservation,
        guest=guest,
        name=name or (str(guest) if guest else "Walk-in"),
        is_primary=is_primary,
        display_currency=reservation.currency if reservation else "ETB",
        bill_to_name=guest.company if guest else "",
        bill_to_tin=guest.company_tin if guest else "",
    )


def primary_folio(reservation):
    folio = reservation.folios.filter(status=Folio.Status.OPEN, is_primary=True).first()
    return folio or reservation.folios.filter(status=Folio.Status.OPEN).first() or open_folio(reservation=reservation)


def folio_totals(folio):
    charges = folio.charges.filter(is_void=False).aggregate(
        net=Sum("net_amount"), service=Sum("service_charge"), vat=Sum("vat"), total=Sum("total")
    )
    paid = money(folio.payments.aggregate(total=Sum("amount_etb"))["total"])
    total = money(charges["total"])
    return {
        "net": money(charges["net"]),
        "service_charge": money(charges["service"]),
        "vat": money(charges["vat"]),
        "total": total,
        "paid": paid,
        "balance": total - paid,
    }


def folio_balance(folio):
    return folio_totals(folio)["balance"]


def reservation_balance(reservation):
    return sum((folio_balance(f) for f in reservation.folios.exclude(status=Folio.Status.VOID)), start=ZERO)


def _require_open(folio):
    if folio.status != Folio.Status.OPEN:
        raise ValidationError(f"Folio {folio.number} is {folio.status}; no more postings allowed.")


def usd_rate(day):
    rate = ExchangeRate.rate_for(day)
    if rate is None:
        raise ValidationError("Enter today's USD exchange rate before posting or taking USD amounts.")
    return rate


@transaction.atomic
def post_charge(folio, *, outlet, description, unit_price, quantity=1, user=None, currency="ETB",
                apply_service_charge=True, apply_vat=True, includes_tax=None, source_type="", source_id="",
                room_night=None, business_date=None):
    folio = Folio.objects.select_for_update().get(pk=folio.pk)
    _require_open(folio)
    if outlet not in Outlet.values:
        raise ValidationError({"outlet": "Unknown outlet."})
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be positive."})
    hotel = HotelSettings.load()
    business_date = business_date or HotelSettings.current_business_date()

    unit_price = Decimal(unit_price)
    original_amount, rate = None, None
    if currency == "USD":
        rate = usd_rate(business_date)
        original_amount = money(unit_price * quantity)
        unit_price_etb = money(unit_price * rate)
    else:
        unit_price_etb = money(unit_price)

    net, service, vat, total = tax_breakdown(
        unit_price_etb * quantity, hotel,
        apply_service_charge=apply_service_charge, apply_vat=apply_vat, includes_tax=includes_tax,
    )
    return Charge.objects.create(
        folio=folio, outlet=outlet, description=description, quantity=quantity, unit_price=unit_price_etb,
        net_amount=net, service_charge=service, vat=vat, total=total, business_date=business_date,
        room_night=room_night, original_currency=currency, original_amount=original_amount, exchange_rate=rate,
        source_type=source_type, source_id=str(source_id or ""), posted_by=user,
    )


@transaction.atomic
def void_charge(charge, *, reason, user=None):
    charge = Charge.objects.select_for_update().select_related("folio").get(pk=charge.pk)
    _require_open(charge.folio)
    if charge.is_void:
        raise ValidationError("This charge is already void.")
    if not reason:
        raise ValidationError({"reason": "A reason is required to void a charge."})
    charge.is_void = True
    charge.void_reason = reason
    charge.voided_by = user
    charge.voided_at = timezone.now()
    charge.save()
    return charge


def open_shift_for(user):
    return CashierShift.objects.filter(cashier=user, status=CashierShift.Status.OPEN).first()


@transaction.atomic
def take_payment(folio, *, method, amount, currency="ETB", reference="", user=None, kind=Payment.Kind.PAYMENT):
    folio = Folio.objects.select_for_update().get(pk=folio.pk)
    _require_open(folio)
    if method not in PaymentMethod.values:
        raise ValidationError({"method": "Unknown payment method."})
    amount = money(amount)
    if amount == 0:
        raise ValidationError({"amount": "Amount cannot be zero."})
    if kind == Payment.Kind.REFUND:
        amount = -abs(amount)
    elif amount < 0:
        raise ValidationError({"amount": "Use a refund for negative amounts."})
    if method in (PaymentMethod.CARD, PaymentMethod.TELEBIRR, PaymentMethod.CBE_BIRR, PaymentMethod.BANK_TRANSFER) and not reference:
        raise ValidationError({"reference": "Enter the transaction reference for non-cash payments."})
    if method == PaymentMethod.CITY_LEDGER and not folio.bill_to_name:
        raise ValidationError({"method": "Set the company (bill-to) on the folio before charging to its account."})

    shift = open_shift_for(user) if user else None
    if shift is None and method != PaymentMethod.CITY_LEDGER:
        raise ValidationError("Open a cashier shift before taking payments.")

    business_date = HotelSettings.current_business_date()
    rate = usd_rate(business_date) if currency == "USD" else Decimal(1)
    payment = Payment.objects.create(
        folio=folio, kind=kind, method=method, currency=currency, amount=amount, exchange_rate=rate,
        amount_etb=money(amount * rate), reference=reference, shift=shift, business_date=business_date,
        received_by=user,
    )
    return payment


@transaction.atomic
def transfer_charges(charges, to_folio, *, user=None):
    """Split a bill: move charges to another folio (e.g. company pays the room)."""
    to_folio = Folio.objects.select_for_update().get(pk=to_folio.pk)
    _require_open(to_folio)
    moved = []
    for charge in charges:
        charge = Charge.objects.select_for_update().select_related("folio").get(pk=charge.pk)
        _require_open(charge.folio)
        if charge.folio_id == to_folio.pk:
            continue
        audit.log("action", charge, description=f"Moved from folio {charge.folio.number} to {to_folio.number}", user=user)
        charge.folio = to_folio
        charge.save(update_fields=["folio"])
        moved.append(charge)
    return moved


@transaction.atomic
def post_room_charges(reservation, *, through, user=None):
    """Post the room rate for every night up to and including `through` that is not yet posted."""
    from apps.reservations.services import nights_between

    if reservation.check_in > through:
        return []
    folio = primary_folio(reservation)
    posted_nights = set(
        Charge.objects.filter(folio__reservation=reservation, room_night__isnull=False, is_void=False)
        .values_list("room_night", flat=True)
    )
    end = min(through + datetime.timedelta(days=1), reservation.check_out)
    created = []
    room_label = reservation.room.number if reservation.room_id else reservation.room_type.code
    for night in nights_between(reservation.check_in, end):
        if night in posted_nights:
            continue
        created.append(post_charge(
            folio, outlet=Outlet.ROOM, description=f"Room {room_label} – night of {night:%d %b %Y}",
            unit_price=reservation.nightly_rate, currency=reservation.currency, user=user,
            source_type="reservation", source_id=reservation.pk, room_night=night, business_date=night,
        ))
    return created


@transaction.atomic
def close_folio(folio, *, user=None, allow_empty=True):
    folio = Folio.objects.select_for_update().get(pk=folio.pk)
    _require_open(folio)
    totals = folio_totals(folio)
    if totals["balance"] != 0:
        raise ValidationError(f"Folio {folio.number} still has a balance of {totals['balance']} ETB.")
    if totals["total"] == 0 and totals["paid"] == 0:
        folio.status = Folio.Status.VOID if allow_empty else folio.status
    else:
        hotel = HotelSettings.load()
        year = timezone.localdate().year
        folio.invoice_number = f"{hotel.invoice_prefix}-{year}-{next_number(f'invoice-{year}'):06d}"
        folio.status = Folio.Status.CLOSED
    folio.closed_at = timezone.now()
    folio.closed_by = user
    folio.save()
    if folio.invoice_number:
        fiscal_no = get_driver().register_invoice(invoice_data(folio))
        if fiscal_no:
            folio.fiscal_receipt_number = fiscal_no
            folio.save(update_fields=["fiscal_receipt_number"])
    return folio


def invoice_data(folio):
    hotel = HotelSettings.load()
    totals = folio_totals(folio)
    issued = folio.closed_at or timezone.now()
    issued_date = timezone.localtime(issued).date()
    guest = folio.guest
    rate = ExchangeRate.rate_for(issued_date) if folio.display_currency == "USD" else None
    lines = [
        {
            "date": c.business_date, "outlet": c.get_outlet_display(), "description": c.description,
            "quantity": c.quantity, "unit_price": c.unit_price, "net": c.net_amount,
            "service_charge": c.service_charge, "vat": c.vat, "total": c.total,
        }
        for c in folio.charges.filter(is_void=False)
    ]
    payments = [
        {
            "date": p.business_date, "method": p.get_method_display(), "kind": p.kind, "currency": p.currency,
            "amount": p.amount, "amount_etb": p.amount_etb, "reference": p.reference,
        }
        for p in folio.payments.all()
    ]
    reservation = folio.reservation
    return {
        "hotel": {
            "name": hotel.name, "address": hotel.address, "phone": hotel.phone, "email": hotel.email,
            "tin": hotel.tin, "vat_registration_no": hotel.vat_registration_no,
            "vat_rate": hotel.vat_rate, "service_charge_rate": hotel.service_charge_rate,
        },
        "invoice_number": folio.invoice_number,
        "folio_number": folio.number,
        "status": folio.status,
        "fiscal_receipt_number": folio.fiscal_receipt_number,
        "issued_at": issued,
        "ethiopian_date": format_ethiopian(issued_date) if hotel.show_ethiopian_date else None,
        "guest": {
            "name": folio.name,
            "nationality": guest.nationality if guest else "",
            "id_number": guest.id_number if guest else "",
        },
        "bill_to": {"name": folio.bill_to_name, "tin": folio.bill_to_tin},
        "stay": {
            "reservation": reservation.code, "room": reservation.room.number if reservation.room_id else None,
            "check_in": reservation.check_in, "check_out": reservation.check_out, "nights": reservation.nights,
        } if reservation else None,
        "lines": lines,
        "payments": payments,
        "totals": totals,
        "currency": "ETB",
        "usd": {
            "rate": rate,
            "total": money(totals["total"] / rate) if rate else None,
            "balance": money(totals["balance"] / rate) if rate else None,
        } if rate else None,
    }


def shift_summary(shift):
    payments = shift.payments.all()
    by_method = {}
    for row in payments.values("method", "currency").annotate(total=Sum("amount"), total_etb=Sum("amount_etb")):
        by_method.setdefault(row["method"], []).append(
            {"currency": row["currency"], "total": row["total"], "total_etb": row["total_etb"]}
        )
    cash_etb = payments.filter(method=PaymentMethod.CASH, currency="ETB").aggregate(t=Sum("amount"))["t"] or ZERO
    cash_usd = payments.filter(method=PaymentMethod.CASH, currency="USD").aggregate(t=Sum("amount"))["t"] or ZERO
    expected_etb = shift.opening_float + cash_etb
    summary = {
        "shift": shift.pk,
        "cashier": str(shift.cashier),
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "status": shift.status,
        "opening_float": shift.opening_float,
        "by_method": by_method,
        "payment_count": payments.count(),
        "total_etb": payments.aggregate(t=Sum("amount_etb"))["t"] or ZERO,
        "expected_cash_etb": expected_etb,
        "expected_cash_usd": cash_usd,
        "counted_cash_etb": shift.counted_cash_etb,
        "counted_cash_usd": shift.counted_cash_usd,
    }
    if shift.counted_cash_etb is not None:
        summary["over_short_etb"] = shift.counted_cash_etb - expected_etb
    if shift.counted_cash_usd is not None:
        summary["over_short_usd"] = shift.counted_cash_usd - cash_usd
    return summary


@transaction.atomic
def close_shift(shift, *, counted_cash_etb, counted_cash_usd=0, notes="", user=None):
    shift = CashierShift.objects.select_for_update().get(pk=shift.pk)
    if shift.status != CashierShift.Status.OPEN:
        raise ValidationError("This shift is already closed.")
    shift.counted_cash_etb = money(counted_cash_etb)
    shift.counted_cash_usd = money(counted_cash_usd or 0)
    shift.notes = notes
    shift.status = CashierShift.Status.CLOSED
    shift.closed_at = timezone.now()
    shift.save()
    return shift
