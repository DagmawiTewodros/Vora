from decimal import Decimal

from django.test import TestCase

from apps.billing.models import Folio
from apps.core.models import HotelSettings
from apps.housekeeping.models import HousekeepingTask
from apps.reservations.models import Reservation
from apps.rooms.models import Room

from .factories import client_for, day, foreign_guest, guest, setup_hotel, staff


class ReservationTests(TestCase):
    def setUp(self):
        self.std, self.dlx = setup_hotel(rooms_per_type=2)
        self.desk = staff("desk", role="front_desk")
        self.client = client_for(self.desk)

    def book(self, **extra):
        data = {"guest": guest().pk, "room_type": self.std.pk, "check_in": day(0).isoformat(), "check_out": day(2).isoformat()}
        data.update(extra)
        return self.client.post("/api/reservations/", data, format="json")

    def test_create_with_new_guest_uses_rate_plan_and_opens_folio(self):
        res = self.client.post("/api/reservations/", {
            "new_guest": {"first_name": "Hana", "last_name": "Tesfaye", "phone": "+251911000000"},
            "room_type": self.std.pk, "check_in": day(0).isoformat(), "check_out": day(3).isoformat(), "source": "phone",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["nightly_rate"], "6000.00")
        self.assertEqual(res.data["nights"], 3)
        self.assertTrue(Folio.objects.filter(reservation_id=res.data["id"], is_primary=True).exists())

    def test_no_double_booking_by_room_type(self):
        self.assertEqual(self.book().status_code, 201)
        self.assertEqual(self.book().status_code, 201)
        res = self.book(check_in=day(1).isoformat(), check_out=day(4).isoformat())
        self.assertEqual(res.status_code, 400)
        self.assertIn("No Standard Double rooms are free", str(res.data))
        # The day both rooms free up, selling works again.
        self.assertEqual(self.book(check_in=day(2).isoformat(), check_out=day(3).isoformat()).status_code, 201)

    def test_no_double_booking_of_a_specific_room(self):
        room = Room.objects.get(number="101")
        self.assertEqual(self.book(room=room.pk).status_code, 201)
        res = self.book(room=room.pk, check_in=day(1).isoformat(), check_out=day(3).isoformat())
        self.assertEqual(res.status_code, 400)
        self.assertIn("already booked", str(res.data))

    def test_out_of_order_rooms_are_not_sold(self):
        manager = client_for(staff("mgr"))
        manager.post(f"/api/rooms/{Room.objects.get(number='101').pk}/out-of-order/", {"reason": "Leak"}, format="json")
        self.assertEqual(self.book().status_code, 201)
        self.assertEqual(self.book().status_code, 400)

    def test_capacity_and_dates_are_validated(self):
        self.assertEqual(self.book(adults=3).status_code, 400)
        self.assertEqual(self.book(check_out=day(0).isoformat()).status_code, 400)

    def test_cancel_releases_inventory(self):
        first = self.book().data
        self.book()
        self.assertEqual(self.book().status_code, 400)
        self.assertEqual(self.client.post(f"/api/reservations/{first['id']}/cancel/", {"reason": "Plans changed"}).status_code, 200)
        self.assertEqual(self.book().status_code, 201)

    def test_update_dates_rechecks_availability(self):
        a = self.book().data
        self.book(check_in=day(2).isoformat(), check_out=day(4).isoformat())
        self.book(check_in=day(2).isoformat(), check_out=day(4).isoformat())
        res = self.client.patch(f"/api/reservations/{a['id']}/", {"check_out": day(3).isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_availability_endpoint(self):
        self.book()
        res = self.client.get(f"/api/availability/?check_in={day(0)}&check_out={day(2)}")
        std = next(r for r in res.data if r["code"] == "STD")
        self.assertEqual(std["available"], 1)
        self.assertEqual(std["quote"]["total"], Decimal("12000.00"))

    def test_waiter_cannot_create_reservations(self):
        waiter = client_for(staff("w", role="waiter"))
        res = waiter.post("/api/reservations/", {"guest": guest().pk, "room_type": self.std.pk,
                                                 "check_in": day(0).isoformat(), "check_out": day(1).isoformat()}, format="json")
        self.assertEqual(res.status_code, 403)


class CheckInOutTests(TestCase):
    def setUp(self):
        self.std, self.dlx = setup_hotel()
        self.desk = staff("desk", role="front_desk")
        self.client = client_for(self.desk)
        self.room = Room.objects.get(number="101")
        res = self.client.post("/api/reservations/", {
            "guest": guest().pk, "room_type": self.std.pk, "room": self.room.pk,
            "check_in": day(0).isoformat(), "check_out": day(2).isoformat(),
        }, format="json")
        self.reservation = res.data

    def url(self, action):
        return f"/api/reservations/{self.reservation['id']}/{action}/"

    def test_check_in_requires_registration_details(self):
        g = guest(id_number="")
        res = self.client.post("/api/reservations/", {"guest": g.pk, "room_type": self.std.pk, "room": Room.objects.get(number="102").pk,
                                                      "check_in": day(0).isoformat(), "check_out": day(1).isoformat()}, format="json")
        res = self.client.post(f"/api/reservations/{res.data['id']}/check-in/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("ID or passport", str(res.data))

    def test_foreign_guest_must_use_passport(self):
        g = foreign_guest(id_type="kebele")
        res = self.client.post("/api/reservations/", {"guest": g.pk, "room_type": self.std.pk, "room": Room.objects.get(number="102").pk,
                                                      "check_in": day(0).isoformat(), "check_out": day(1).isoformat()}, format="json")
        self.assertEqual(self.client.post(f"/api/reservations/{res.data['id']}/check-in/").status_code, 400)

    def test_dirty_room_blocks_check_in(self):
        Room.objects.filter(pk=self.room.pk).update(housekeeping_status="dirty")
        res = self.client.post(self.url("check-in"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("not been cleaned", str(res.data))

    def test_future_reservation_cannot_check_in(self):
        res = self.client.post("/api/reservations/", {"guest": guest().pk, "room_type": self.dlx.pk,
                                                      "check_in": day(5).isoformat(), "check_out": day(6).isoformat()}, format="json")
        self.assertEqual(self.client.post(f"/api/reservations/{res.data['id']}/check-in/", {"room": Room.objects.get(number="201").pk}).status_code, 400)

    def test_full_stay(self):
        res = self.client.post(self.url("check-in"))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "checked_in")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "occupied")

        # Check-out posts both room nights (6000 net + 10% SC + 15% VAT each) and needs payment first.
        HotelSettings.objects.filter(pk=1).update(business_date=day(2))
        res = self.client.post(self.url("check-out"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("15180.00", str(res.data))

        folio = Folio.objects.get(reservation_id=self.reservation["id"])
        self.client.post("/api/shifts/", {"opening_float": "1000"}, format="json")
        res = self.client.post(f"/api/folios/{folio.pk}/payments/", {"method": "telebirr", "amount": "15180", "reference": "TB123"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["totals"]["balance"], "0.00")

        res = self.client.post(self.url("check-out"))
        self.assertEqual(res.status_code, 200, res.data)
        folio.refresh_from_db()
        self.assertEqual(folio.status, "closed")
        self.assertRegex(folio.invoice_number, r"^VA-\d{4}-000001$")
        self.room.refresh_from_db()
        self.assertEqual((self.room.status, self.room.housekeeping_status), ("vacant", "dirty"))
        self.assertTrue(HousekeepingTask.objects.filter(room=self.room, task_type="departure", status="open").exists())

        invoice = self.client.get(f"/api/folios/{folio.pk}/invoice/").data
        self.assertEqual(invoice["hotel"]["tin"], "0012345678")
        self.assertEqual(invoice["totals"]["vat"], Decimal("1980.00"))
        self.assertTrue(invoice["ethiopian_date"].endswith("E.C."))

    def test_early_departure_releases_nights(self):
        self.client.post(self.url("check-in"))
        folio = Folio.objects.get(reservation_id=self.reservation["id"])
        self.client.post("/api/shifts/", {}, format="json")
        self.client.post(f"/api/folios/{folio.pk}/payments/", {"method": "cash", "amount": "7590"}, format="json")
        HotelSettings.objects.filter(pk=1).update(business_date=day(1))
        res = self.client.post(self.url("check-out"))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Reservation.objects.get(pk=self.reservation["id"]).check_out, day(1))

    def test_room_move(self):
        self.client.post(self.url("check-in"))
        res = self.client.post(self.url("move-room"), {"room": Room.objects.get(number="102").pk, "reason": "Noise"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["room_number"], "102")
        self.room.refresh_from_db()
        self.assertEqual(self.room.housekeeping_status, "dirty")

    def test_front_desk_board(self):
        board = self.client.get("/api/front-desk/").data
        self.assertEqual(len(board["arrivals"]), 1)
        self.client.post(self.url("check-in"))
        board = self.client.get("/api/front-desk/").data
        self.assertEqual((len(board["arrivals"]), len(board["in_house"])), (0, 1))
