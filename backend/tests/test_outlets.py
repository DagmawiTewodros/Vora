import uuid
from decimal import Decimal

from django.test import TestCase

from apps.billing.models import Folio
from apps.core.models import HotelSettings
from apps.housekeeping.models import HousekeepingTask
from apps.inventory.models import InventoryItem, RecipeLine
from apps.laundry.models import LaundryPrice
from apps.pos.models import Order
from apps.rooms.models import Room

from .factories import client_for, day, guest, menu, setup_hotel, staff


class OutletTestCase(TestCase):
    def setUp(self):
        self.std, _ = setup_hotel()
        self.restaurant, self.bar, self.tibs, self.beer = menu()
        desk = client_for(staff("desk", role="front_desk"))
        res = desk.post("/api/reservations/", {"guest": guest().pk, "room_type": self.std.pk, "room": Room.objects.get(number="101").pk,
                                               "check_in": day(0).isoformat(), "check_out": day(2).isoformat()}, format="json")
        self.reservation = res.data
        desk.post(f"/api/reservations/{res.data['id']}/check-in/")
        self.folio = Folio.objects.get(reservation_id=res.data["id"])
        self.waiter = staff("waiter", role="waiter")
        self.client = client_for(self.waiter)


class PosTests(OutletTestCase):
    def new_order(self, **extra):
        data = {"outlet": self.restaurant.pk, "table": "T4", "items": [
            {"menu_item": self.tibs.pk, "quantity": 2}, {"menu_item": self.beer.pk, "quantity": 3}]}
        data.update(extra)
        return self.client.post("/api/pos/orders/", data, format="json")

    def test_post_to_room_lands_on_guest_folio(self):
        order = self.new_order().data
        self.assertEqual(order["subtotal"], "1260.00")
        self.client.post(f"/api/pos/orders/{order['id']}/send/")
        tickets = self.client.get("/api/pos/kitchen/").data
        self.assertEqual([i["name"] for i in tickets[0]["items"]], ["Beef tibs"])  # beer skips the kitchen

        res = self.client.post(f"/api/pos/orders/{order['id']}/settle/", {"type": "room", "room": "101"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["settlement"], "room")
        self.assertEqual(self.folio.charges.count(), 2)
        self.assertEqual(sum(c.total for c in self.folio.charges.all()), Decimal("1593.90"))

    def test_post_to_empty_room_fails(self):
        order = self.new_order().data
        res = self.client.post(f"/api/pos/orders/{order['id']}/settle/", {"type": "room", "room": "102"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "open")

    def test_pay_at_outlet_with_change(self):
        self.client.post("/api/shifts/", {}, format="json")
        order = self.new_order(items=[{"menu_item": self.beer.pk, "quantity": 1}]).data
        res = self.client.post(f"/api/pos/orders/{order['id']}/settle/", {
            "type": "direct", "payments": [{"method": "cash", "amount": "200"}]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        folio = Folio.objects.get(pk=res.data["folio"])
        self.assertEqual(folio.status, "closed")
        self.assertTrue(folio.invoice_number)
        self.assertEqual(folio.payments.get(kind="refund").amount_etb, Decimal("-48.20"))

    def test_short_payment_is_rejected(self):
        self.client.post("/api/shifts/", {}, format="json")
        order = self.new_order().data
        res = self.client.post(f"/api/pos/orders/{order['id']}/settle/", {
            "type": "direct", "payments": [{"method": "cash", "amount": "100"}]}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "open")

    def test_item_not_sold_at_outlet(self):
        res = self.client.post("/api/pos/orders/", {"outlet": self.bar.pk, "items": [{"menu_item": self.tibs.pk}]}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_offline_sync_is_idempotent(self):
        payload = {"orders": [{
            "client_uuid": str(uuid.uuid4()), "outlet": self.bar.pk, "items": [{"menu_item": self.beer.pk, "quantity": 2}],
            "settlement": {"type": "room", "room": "101"},
        }]}
        first = self.client.post("/api/pos/orders/sync/", payload, format="json").data
        second = self.client.post("/api/pos/orders/sync/", payload, format="json").data
        self.assertTrue(first["results"][0]["ok"])
        self.assertEqual(first["results"][0]["order"]["id"], second["results"][0]["order"]["id"])
        self.assertEqual(self.folio.charges.count(), 1)

    def test_offline_sync_reports_failures_per_order(self):
        payload = {"orders": [
            {"client_uuid": str(uuid.uuid4()), "outlet": self.bar.pk, "items": [{"menu_item": self.beer.pk}],
             "settlement": {"type": "room", "room": "999"}},
            {"client_uuid": str(uuid.uuid4()), "outlet": self.bar.pk, "items": [{"menu_item": self.beer.pk}],
             "settlement": {"type": "room", "room": "101"}},
        ]}
        results = self.client.post("/api/pos/orders/sync/", payload, format="json").data["results"]
        self.assertEqual([r["ok"] for r in results], [False, True])
        self.assertEqual(Order.objects.count(), 1)

    def test_recipe_stock_is_deducted(self):
        beef = InventoryItem.objects.create(name="Beef", sku="BEEF", unit="kg", stock=Decimal("10"), reorder_level=Decimal("2"))
        RecipeLine.objects.create(menu_item=self.tibs, inventory_item=beef, quantity=Decimal("0.250"))
        order = self.new_order().data
        self.client.post(f"/api/pos/orders/{order['id']}/settle/", {"type": "room", "room": "101"}, format="json")
        beef.refresh_from_db()
        self.assertEqual(beef.stock, Decimal("9.500"))

    def test_breakfast_log(self):
        res = self.client.post("/api/pos/breakfast/", {"reservation": self.reservation["id"], "covers": 1}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self.client.post("/api/pos/breakfast/", {"reservation": self.reservation["id"]}, format="json").status_code, 400)


class LaundryTests(OutletTestCase):
    def test_ticket_is_billed_on_delivery(self):
        shirt = LaundryPrice.objects.create(item="Shirt", service="wash", price=Decimal("80"))
        suit = LaundryPrice.objects.create(item="Suit", service="dry_clean", price=Decimal("350"))
        laundry = client_for(staff("laundry", role="laundry"))
        res = laundry.post("/api/laundry/tickets/", {"reservation": self.reservation["id"], "express": True,
                                                     "lines": [{"price": shirt.pk, "quantity": 3}, {"price": suit.pk, "quantity": 1}]}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["total"], "885.00")
        ticket = res.data["id"]
        for _ in range(3):
            res = laundry.post(f"/api/laundry/tickets/{ticket}/advance/")
        self.assertEqual(res.data["status"], "delivered")
        self.assertTrue(res.data["posted"])
        self.assertEqual(sum(c.net_amount for c in self.folio.charges.filter(outlet="laundry")), Decimal("885.00"))
        self.assertEqual(laundry.post(f"/api/laundry/tickets/{ticket}/advance/").status_code, 400)


class HousekeepingTests(OutletTestCase):
    def test_departure_clean_then_inspection(self):
        room = Room.objects.get(number="102")
        hk = client_for(staff("hk", role="housekeeping"))
        hk.post(f"/api/housekeeping/rooms/{room.pk}/set-status/", {"housekeeping_status": "dirty"}, format="json")
        task = HousekeepingTask.objects.get(room=room)
        hk.post(f"/api/housekeeping/tasks/{task.pk}/start/")
        hk.post(f"/api/housekeeping/tasks/{task.pk}/complete/")
        room.refresh_from_db()
        self.assertEqual(room.housekeeping_status, "clean")
        inspection = HousekeepingTask.objects.get(room=room, task_type="inspection")
        hk.post(f"/api/housekeeping/tasks/{inspection.pk}/complete/")
        room.refresh_from_db()
        self.assertEqual(room.housekeeping_status, "inspected")

    def test_night_audit_creates_stayover_tasks(self):
        client_for(staff("mgr")).post("/api/reports/night-audit/run/")
        self.assertTrue(HousekeepingTask.objects.filter(room__number="101", task_type="stayover").exists())
        self.assertEqual(HotelSettings.load().business_date, day(1))
