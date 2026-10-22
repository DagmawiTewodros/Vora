from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def tax_breakdown(amount, hotel, *, apply_service_charge=True, apply_vat=True, includes_tax=None):
    """Split an amount into (net, service_charge, vat, total).

    Ethiopian hotels add a service charge to the price and then VAT; whether VAT
    also applies to the service charge is configurable in HotelSettings. When
    prices already include tax, the net is worked back from the gross so the
    total equals the price exactly.
    """
    if includes_tax is None:
        includes_tax = hotel.prices_include_tax
    sc_rate = hotel.service_charge_rate if apply_service_charge else Decimal(0)
    vat_rate = hotel.vat_rate if apply_vat else Decimal(0)

    if includes_tax:
        gross = money(amount)
        if hotel.vat_on_service_charge:
            factor = (1 + sc_rate) * (1 + vat_rate)
        else:
            factor = 1 + sc_rate + vat_rate
        net = money(gross / factor)
        service = money(net * sc_rate)
        vat = gross - net - service
        return net, service, vat, gross

    net = money(amount)
    service = money(net * sc_rate)
    vat_base = net + service if hotel.vat_on_service_charge else net
    vat = money(vat_base * vat_rate)
    return net, service, vat, net + service + vat
