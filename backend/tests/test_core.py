import datetime
from decimal import Decimal

from django.test import TestCase

from apps.core.ethiopian import format_ethiopian, to_ethiopian
from apps.core.models import AuditLog, HotelSettings
from apps.core.money import tax_breakdown

from .factories import client_for, setup_hotel, staff


class TaxTests(TestCase):
    def test_service_charge_then_vat_on_top(self):
        hotel = HotelSettings.load()
        net, service, vat, total = tax_breakdown(Decimal("1000"), hotel, includes_tax=False)
        self.assertEqual((net, service, vat, total), (Decimal("1000.00"), Decimal("100.00"), Decimal("165.00"), Decimal("1265.00")))

    def test_vat_on_net_only_when_configured(self):
        hotel = HotelSettings.load()
        hotel.vat_on_service_charge = False
        _, service, vat, total = tax_breakdown(Decimal("1000"), hotel, includes_tax=False)
        self.assertEqual((service, vat, total), (Decimal("100.00"), Decimal("150.00"), Decimal("1250.00")))

    def test_tax_inclusive_price_keeps_total(self):
        hotel = HotelSettings.load()
        net, service, vat, total = tax_breakdown(Decimal("1265"), hotel, includes_tax=True)
        self.assertEqual(total, Decimal("1265.00"))
        self.assertEqual(net, Decimal("1000.00"))
        self.assertEqual(net + service + vat, total)


class EthiopianCalendarTests(TestCase):
    def test_known_dates(self):
        self.assertEqual(to_ethiopian(datetime.date(2023, 9, 12)), (2016, 1, 1))
        self.assertEqual(to_ethiopian(datetime.date(2024, 1, 7)), (2016, 4, 28))  # Genna
        self.assertEqual(to_ethiopian(datetime.date(2023, 9, 11)), (2015, 13, 6))  # Pagume 6 in a leap year
        self.assertEqual(to_ethiopian(datetime.date(2026, 9, 11)), (2019, 1, 1))

    def test_format(self):
        self.assertEqual(format_ethiopian(datetime.date(2026, 10, 22)), "Tikimt 12, 2019 E.C.")
        self.assertIn("ዓ.ም.", format_ethiopian(datetime.date(2026, 10, 22), "am"))


class AuthTests(TestCase):
    def test_password_and_pin_login(self):
        user = staff("selam", role="waiter")
        user.set_pin("4321")
        user.save()
        client = client_for(user)
        client.force_authenticate(None)
        self.assertEqual(client.post("/api/auth/login/", {"username": "selam", "password": "pass-12345"}).status_code, 200)
        self.assertEqual(client.post("/api/auth/pin/", {"username": "selam", "pin": "0000"}).status_code, 401)
        res = client.post("/api/auth/pin/", {"username": "selam", "pin": "4321"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["role"], "waiter")

    def test_staff_management_is_manager_only(self):
        waiter = staff("waiter", role="waiter")
        self.assertEqual(client_for(waiter).get("/api/staff/").status_code, 403)
        manager = staff("boss")
        res = client_for(manager).post("/api/staff/", {"username": "new", "role": "cashier", "pin": "1234"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["has_pin"])


class AuditTests(TestCase):
    def test_changes_are_logged_with_user(self):
        setup_hotel()
        manager = staff()
        client = client_for(manager)
        room = client.get("/api/rooms/").data[0]
        client.patch(f"/api/rooms/{room['id']}/", {"notes": "Balcony door sticks"}, format="json")
        entry = AuditLog.objects.filter(model="rooms.Room", action="update").first()
        self.assertEqual(entry.user, manager)
        self.assertEqual(entry.after, {"notes": "Balcony door sticks"})
