from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.distribution.models import ChannelConnection
from apps.inventory.models import InventoryItem, Supplier
from apps.reports.models import NightAudit
from apps.reservations.models import Reservation
from apps.rooms.models import Room

from .factories import client_for, day, foreign_guest, guest, setup_hotel, staff


class ReportTests(TestCase):
    def setUp(self):
        self.std, self.dlx = setup_hotel(rooms_per_type=2)  # 4 rooms
        self.manager = client_for(staff("mgr"))
        for number, g in (("101", guest()), ("201", foreign_guest())):
            room = Room.objects.get(number=number)
            res = self.manager.post("/api/reservations/", {"guest": g.pk, "room_type": room.room_type_id, "room": room.pk,
                                                           "check_in": day(0).isoformat(), "check_out": day(3).isoformat()}, format="json")
            self.manager.post(f"/api/reservations/{res.data['id']}/check-in/")

    def test_night_audit_and_daily_kpis(self):
        res = self.manager.post("/api/reports/night-audit/run/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["summary"]["room_nights_posted"], 2)
        self.assertEqual(self.manager.post("/api/reports/night-audit/run/").status_code, 200)  # next day
        self.assertEqual(NightAudit.objects.count(), 2)

        report = self.manager.get(f"/api/reports/daily/?date={day(0)}").data
        self.assertEqual(report["rooms_sold"], 2)
        self.assertEqual(report["occupancy_pct"], 50.0)
        self.assertEqual(report["room_revenue"], Decimal("14000.00"))
        self.assertEqual(report["adr"], Decimal("7000.00"))
        self.assertEqual(report["revpar"], Decimal("3500.00"))

        summary = self.manager.get(f"/api/reports/summary/?start={day(0)}&end={day(1)}").data
        self.assertEqual(summary["totals"]["rooms_sold"], 4)

    def test_night_audit_cannot_run_twice_for_the_same_day(self):
        from apps.core.models import HotelSettings

        self.manager.post("/api/reports/night-audit/run/")
        HotelSettings.objects.filter(pk=1).update(business_date=day(0))
        self.assertEqual(self.manager.post("/api/reports/night-audit/run/").status_code, 400)

    def test_guest_register_and_permissions(self):
        register = self.manager.get(f"/api/reports/guest-register/?date={day(0)}").data
        self.assertEqual({g["room"] for g in register["guests"]}, {"101", "201"})
        self.assertIn("GB998877", [g["id_number"] for g in register["guests"]])
        waiter = client_for(staff("w", role="waiter"))
        self.assertEqual(waiter.get("/api/reports/daily/").status_code, 403)
        self.assertEqual(waiter.get("/api/reports/guest-register/").status_code, 400)

    def test_breakfast_report(self):
        report = self.manager.get(f"/api/reports/breakfast/?date={day(1)}").data
        self.assertEqual(report["entitled_covers"], 2)


@override_settings(REST_FRAMEWORK={
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {},
})
class ChannelTests(TestCase):
    def setUp(self):
        self.std, _ = setup_hotel(rooms_per_type=1)
        self.channel = ChannelConnection.objects.create(name="Expedia", code="expedia", is_active=True, webhook_secret="s3cret")
        self.public = APIClient()

    def booking(self, **extra):
        data = {"reference": "EXP-1", "room_type": "STD", "check_in": day(0).isoformat(), "check_out": day(2).isoformat(),
                "guest": {"first_name": "Tom", "last_name": "Smith", "nationality": "US"}, "nightly_rate": "75", "currency": "USD"}
        data.update(extra)
        return data

    def post(self, data, secret="s3cret"):
        return self.public.post("/api/channels/webhook/expedia/", data, format="json", HTTP_X_VORA_SECRET=secret)

    def test_ota_booking_is_idempotent_and_blocks_inventory(self):
        self.assertEqual(self.post(self.booking(), secret="wrong").status_code, 403)
        first = self.post(self.booking())
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(self.post(self.booking()).data["reservation"], first.data["reservation"])
        reservation = Reservation.objects.get(code=first.data["reservation"])
        self.assertEqual((reservation.source, reservation.nightly_rate, reservation.currency), ("ota", Decimal("75.00"), "USD"))

        # Only one STD room: a second OTA booking for the same nights is refused.
        self.assertEqual(self.post(self.booking(reference="EXP-2")).status_code, 400)

        self.post(self.booking(status="cancelled"))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "cancelled")

    def test_push_respects_stop_sell(self):
        manager = client_for(staff("mgr"))
        payload = manager.post(f"/api/channels/{self.channel.pk}/push/", {"days": 3}, format="json").data
        std = next(r for r in payload["rooms"] if r["room_type"] == "STD")
        self.assertEqual(std["nights"][0]["available"], 1)
        manager.post(f"/api/channels/{self.channel.pk}/stop-sell/", {"stop_sell": True}, format="json")
        payload = manager.post(f"/api/channels/{self.channel.pk}/push/", {"days": 3}, format="json").data
        self.assertTrue(all(n["available"] == 0 for r in payload["rooms"] for n in r["nights"]))

    def test_booking_engine(self):
        from django.utils import timezone

        start = timezone.localdate()
        end = start + __import__("datetime").timedelta(days=2)
        offers = self.public.get(f"/api/public/availability/?check_in={start}&check_out={end}").data["offers"]
        self.assertEqual({o["room_type"] for o in offers}, {"STD", "DLX"})
        res = self.public.post("/api/public/book/", {
            "room_type": "STD", "check_in": start.isoformat(), "check_out": end.isoformat(), "first_name": "Liya",
            "last_name": "Alemu", "email": "liya@example.com", "phone": "+251911223344",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["status"], "tentative")
        offers = self.public.get(f"/api/public/availability/?check_in={start}&check_out={end}").data["offers"]
        self.assertEqual({o["room_type"] for o in offers}, {"DLX"})


class InventoryTests(TestCase):
    def test_purchase_order_receipt_updates_stock(self):
        store = client_for(staff("store", role="store_keeper"))
        supplier = Supplier.objects.create(name="Shoa Supermarket")
        item = InventoryItem.objects.create(name="Coffee beans", sku="COF", unit="kg", reorder_level=Decimal("5"))
        self.assertEqual(len(store.get("/api/inventory/items/?low=true").data), 1)
        po = store.post("/api/inventory/purchase-orders/", {"supplier": supplier.pk, "lines": [
            {"item": item.pk, "quantity": "20", "unit_cost": "900"}]}, format="json").data
        self.assertEqual(po["total"], "18000.00")
        line_id = po["lines"][0]["id"]
        store.post(f"/api/inventory/purchase-orders/{po['id']}/mark-ordered/")
        res = store.post(f"/api/inventory/purchase-orders/{po['id']}/receive/", {"received": {str(line_id): "18"}}, format="json")
        self.assertEqual(res.data["status"], "received")
        item.refresh_from_db()
        self.assertEqual(item.stock, Decimal("18.000"))
        store.post(f"/api/inventory/items/{item.pk}/count/", {"counted": "17.5"}, format="json")
        item.refresh_from_db()
        self.assertEqual(item.stock, Decimal("17.500"))
        self.assertEqual(len(store.get("/api/inventory/items/?low=true").data), 0)
