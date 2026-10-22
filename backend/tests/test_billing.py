from decimal import Decimal

from django.test import TestCase

from apps.billing.models import Folio
from apps.core.models import ExchangeRate, HotelSettings
from apps.rooms.models import Room

from .factories import client_for, day, foreign_guest, setup_hotel, staff


class FolioTests(TestCase):
    def setUp(self):
        self.std, _ = setup_hotel()
        self.desk = staff("desk", role="front_desk")
        self.client = client_for(self.desk)
        res = self.client.post("/api/reservations/", {
            "guest": foreign_guest().pk, "room_type": self.std.pk, "room": Room.objects.get(number="101").pk,
            "check_in": day(0).isoformat(), "check_out": day(1).isoformat(), "currency": "USD",
        }, format="json")
        self.reservation = res.data
        self.folio = Folio.objects.get(reservation_id=res.data["id"])
        self.client.post(f"/api/reservations/{res.data['id']}/check-in/")

    def test_usd_room_rate_posts_in_etb_at_the_day_rate(self):
        self.assertEqual(self.reservation["nightly_rate"], "70.00")
        self.client.post("/api/reports/night-audit/run/")  # needs a manager
        manager = client_for(staff("mgr"))
        res = manager.post("/api/reports/night-audit/run/")
        self.assertEqual(res.status_code, 200, res.data)
        charge = self.folio.charges.get()
        self.assertEqual(charge.unit_price, Decimal("10500.00"))  # 70 USD × 150
        self.assertEqual(charge.original_amount, Decimal("70.00"))
        self.assertEqual(HotelSettings.load().business_date, day(1))

    def test_usd_payment_is_converted(self):
        self.client.post(f"/api/folios/{self.folio.pk}/charges/", {"outlet": "minibar", "description": "Water", "unit_price": "100"}, format="json")
        self.client.post("/api/shifts/", {}, format="json")
        res = self.client.post(f"/api/folios/{self.folio.pk}/payments/", {"method": "cash", "amount": "1", "currency": "USD"}, format="json")
        payment = res.data["payments"][0]
        self.assertEqual(payment["amount_etb"], "150.00")
        self.assertEqual(res.data["totals"]["balance"], str(Decimal("126.50") - Decimal("150.00")))

    def test_usd_needs_an_exchange_rate(self):
        ExchangeRate.objects.all().delete()
        self.client.post("/api/shifts/", {}, format="json")
        res = self.client.post(f"/api/folios/{self.folio.pk}/payments/", {"method": "cash", "amount": "10", "currency": "USD"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("exchange rate", str(res.data))

    def test_payments_need_an_open_shift_and_references(self):
        url = f"/api/folios/{self.folio.pk}/payments/"
        self.assertIn("cashier shift", str(self.client.post(url, {"method": "cash", "amount": "10"}, format="json").data))
        self.client.post("/api/shifts/", {}, format="json")
        self.assertEqual(self.client.post("/api/shifts/", {}, format="json").status_code, 400)  # one open shift each
        self.assertIn("reference", str(self.client.post(url, {"method": "card", "amount": "10"}, format="json").data))

    def test_refund_is_manager_only(self):
        self.client.post("/api/shifts/", {}, format="json")
        res = self.client.post(f"/api/folios/{self.folio.pk}/payments/", {"method": "cash", "amount": "10", "kind": "refund"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_split_bill(self):
        url = f"/api/folios/{self.folio.pk}/charges/"
        self.client.post(url, {"outlet": "restaurant", "description": "Dinner", "unit_price": "800"}, format="json")
        self.client.post(url, {"outlet": "bar", "description": "Drinks", "unit_price": "300"}, format="json")
        company = self.client.post("/api/folios/split/", {"reservation": self.reservation["id"], "name": "ACME PLC",
                                                          "bill_to_name": "ACME PLC", "bill_to_tin": "0099887766"}, format="json").data
        dinner = self.folio.charges.get(description="Dinner")
        res = self.client.post(f"/api/folios/{self.folio.pk}/transfer/", {"to_folio": company["id"], "charges": [dinner.pk]}, format="json")
        self.assertEqual(len(res.data["charges"]), 1)
        company_folio = Folio.objects.get(pk=company["id"])
        self.assertEqual(company_folio.charges.get().description, "Dinner")

    def test_void_charge_needs_cashier_and_reason(self):
        self.client.post(f"/api/folios/{self.folio.pk}/charges/", {"outlet": "other", "description": "Phone", "unit_price": "50"}, format="json")
        charge = self.folio.charges.get()
        self.assertEqual(self.client.post(f"/api/charges/{charge.pk}/void/", {"reason": "Wrong room"}).status_code, 400)
        cashier = client_for(staff("cash", role="cashier"))
        self.assertEqual(cashier.post(f"/api/charges/{charge.pk}/void/", {}).status_code, 400)
        self.assertEqual(cashier.post(f"/api/charges/{charge.pk}/void/", {"reason": "Wrong room"}).status_code, 200)

    def test_cannot_close_with_balance(self):
        self.client.post(f"/api/folios/{self.folio.pk}/charges/", {"outlet": "other", "description": "Phone", "unit_price": "50"}, format="json")
        self.assertEqual(self.client.post(f"/api/folios/{self.folio.pk}/close/").status_code, 400)


class ShiftTests(TestCase):
    def test_shift_close_reports_over_short(self):
        setup_hotel()
        cashier = staff("cash", role="cashier")
        client = client_for(cashier)
        shift = client.post("/api/shifts/", {"opening_float": "500"}, format="json").data
        folio = client.post("/api/folios/walk-in/", {"name": "Walk-in"}, format="json").data
        client.post(f"/api/folios/{folio['id']}/charges/", {"outlet": "cafe", "description": "Macchiato", "unit_price": "100"}, format="json")
        client.post(f"/api/folios/{folio['id']}/payments/", {"method": "cash", "amount": "126.50"}, format="json")
        res = client.post(f"/api/shifts/{shift['id']}/close/", {"counted_cash_etb": "620"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["expected_cash_etb"], Decimal("626.50"))
        self.assertEqual(res.data["over_short_etb"], Decimal("-6.50"))


class InvoiceNumberTests(TestCase):
    def test_numbers_are_sequential(self):
        setup_hotel()
        client = client_for(staff("cash", role="cashier"))
        client.post("/api/shifts/", {}, format="json")
        numbers = []
        for _ in range(3):
            folio = client.post("/api/folios/walk-in/", {}, format="json").data
            client.post(f"/api/folios/{folio['id']}/charges/", {"outlet": "cafe", "description": "Tea", "unit_price": "40"}, format="json")
            client.post(f"/api/folios/{folio['id']}/payments/", {"method": "cash", "amount": "50.60"}, format="json")
            numbers.append(client.post(f"/api/folios/{folio['id']}/close/").data["invoice_number"])
        self.assertEqual([n[-6:] for n in numbers], ["000001", "000002", "000003"])
        self.assertTrue(all(n.startswith("VA-") for n in numbers))
