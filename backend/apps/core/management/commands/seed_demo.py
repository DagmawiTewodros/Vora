"""Load demo data so the system can be tried end to end.

Room counts, prices and menus are placeholders until Vora Addis confirms the
real figures (see the open questions in docs/IMPLEMENTATION_PLAN.md).
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import ExchangeRate, HotelSettings, Role, Staff
from apps.distribution.models import ChannelConnection
from apps.inventory.models import InventoryItem, RecipeLine, Supplier
from apps.laundry.models import LaundryPrice
from apps.pos.models import MenuCategory, MenuItem, Outlet
from apps.rooms.models import RatePlan, Room, RoomType

ROOM_TYPES = [
    # name, code, capacity, ETB, USD, rooms per floor on floors 1-4
    ("Standard Single", "SGL", 1, "4500", "55", 2),
    ("Standard Double", "DBL", 2, "5500", "65", 3),
    ("Twin Room", "TWN", 2, "5800", "70", 2),
    ("Deluxe King", "DLX", 3, "7500", "90", 2),
    ("Junior Suite", "JST", 3, "10500", "125", 1),
]

STAFF = [
    ("manager", "Meron", "Manager", Role.MANAGER, "1111"),
    ("frontdesk", "Hana", "Reception", Role.FRONT_DESK, "2222"),
    ("cashier", "Dawit", "Cashier", Role.CASHIER, "3333"),
    ("housekeeper", "Tigist", "Housekeeping", Role.HOUSEKEEPING, "4444"),
    ("waiter", "Yonas", "Waiter", Role.WAITER, "5555"),
    ("laundry", "Almaz", "Laundry", Role.LAUNDRY, "6666"),
    ("store", "Bereket", "Store", Role.STORE_KEEPER, "7777"),
    ("revenue", "Sara", "Revenue", Role.REVENUE, "8888"),
]

MENU = [
    # category, name, Amharic, price, outlets, kitchen, breakfast
    ("Breakfast", "Continental breakfast", "ቁርስ", "450", ["restaurant"], True, True),
    ("Breakfast", "Firfir", "ፍርፍር", "320", ["restaurant", "cafe"], True, True),
    ("Breakfast", "Chechebsa", "ጨጨብሳ", "300", ["restaurant", "cafe"], True, True),
    ("Mains", "Special kitfo", "ልዩ ክትፎ", "750", ["restaurant"], True, False),
    ("Mains", "Beef tibs", "ጥብስ", "650", ["restaurant", "bar"], True, False),
    ("Mains", "Doro wat", "ዶሮ ወጥ", "800", ["restaurant"], True, False),
    ("Mains", "Beyaynetu (fasting platter)", "በያይነቱ", "450", ["restaurant"], True, False),
    ("Mains", "Grilled tilapia", "አሳ ጥብስ", "700", ["restaurant"], True, False),
    ("Mains", "Club sandwich", "ክለብ ሳንድዊች", "520", ["restaurant", "cafe", "bar"], True, False),
    ("Hot drinks", "Macchiato", "ማኪያቶ", "80", ["cafe", "restaurant"], False, False),
    ("Hot drinks", "Ethiopian coffee ceremony", "ጀበና ቡና", "150", ["cafe", "restaurant"], False, False),
    ("Hot drinks", "Spris", "ስፕሪስ", "120", ["cafe"], False, False),
    ("Cold drinks", "Ambo mineral water", "አምቦ ውሃ", "60", ["restaurant", "bar", "cafe"], False, False),
    ("Cold drinks", "Fresh avocado juice", "የአቮካዶ ጭማቂ", "180", ["cafe", "restaurant"], False, False),
    ("Bar", "St. George beer", "ቅዱስ ጊዮርጊስ ቢራ", "120", ["bar", "restaurant"], False, False),
    ("Bar", "Habesha beer", "ሐበሻ ቢራ", "120", ["bar", "restaurant"], False, False),
    ("Bar", "Tej (glass)", "ጠጅ", "200", ["bar"], False, False),
    ("Bar", "House red wine (glass)", "ቀይ ወይን", "350", ["bar", "restaurant"], False, False),
]

LAUNDRY = [
    ("Shirt", "ሸሚዝ", {"wash": "80", "press": "40"}),
    ("Trousers", "ሱሪ", {"wash": "100", "press": "50", "dry_clean": "180"}),
    ("Dress", "ቀሚስ", {"wash": "150", "dry_clean": "250"}),
    ("Suit (2 pieces)", "ሙሉ ልብስ", {"dry_clean": "450", "press": "150"}),
    ("Habesha kemis", "የሐበሻ ቀሚስ", {"dry_clean": "400"}),
    ("Underwear / socks", "የውስጥ ልብስ", {"wash": "40"}),
]


class Command(BaseCommand):
    help = "Load demo rooms, rates, staff, menus and prices (safe to run more than once)."

    @transaction.atomic
    def handle(self, *args, **options):
        hotel = HotelSettings.load()
        hotel.business_date = hotel.business_date or timezone.localdate()
        hotel.phone = hotel.phone or "+251 11 000 0000"
        hotel.save()
        ExchangeRate.objects.get_or_create(date=timezone.localdate(), defaults={"usd_to_etb": Decimal("150.00")})

        if not Staff.objects.filter(username="admin").exists():
            Staff.objects.create_superuser("admin", "admin@example.com", "admin12345", role=Role.ADMIN, first_name="System")
        for username, first, last, role, pin in STAFF:
            user, created = Staff.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last, "role": role})
            if created:
                user.set_password("vora12345")
                user.set_pin(pin)
                user.save()

        for order, (name, code, capacity, etb, usd, _per_floor) in enumerate(ROOM_TYPES):
            room_type, _ = RoomType.objects.get_or_create(code=code, defaults={
                "name": name, "capacity": capacity, "base_rate_etb": Decimal(etb), "base_rate_usd": Decimal(usd), "sort_order": order,
                "amenities": "Free Wi-Fi, flat-screen TV, private bathroom",
            })
            RatePlan.objects.get_or_create(room_type=room_type, code="BB", defaults={
                "name": "Bed & Breakfast", "price_etb": Decimal(etb), "price_usd": Decimal(usd), "breakfast_included": True,
            })
            RatePlan.objects.get_or_create(room_type=room_type, code="CORP", defaults={
                "name": "Corporate", "price_etb": Decimal(etb) * Decimal("0.9"), "price_usd": Decimal(usd) * Decimal("0.9"),
                "is_corporate": True, "is_public": False,
            })
        number = {floor: 1 for floor in range(1, 5)}
        for floor in range(1, 5):
            for _name, code, *_rest, per_floor in ROOM_TYPES:
                for _ in range(per_floor):
                    Room.objects.get_or_create(number=f"{floor}{number[floor]:02d}", defaults={
                        "floor": floor, "room_type": RoomType.objects.get(code=code),
                    })
                    number[floor] += 1

        outlets = {}
        for name, kind, kitchen in (("Restaurant", "restaurant", True), ("Bar", "bar", True), ("Café", "cafe", False),
                                    ("Room service", "room_service", True)):
            outlets[kind], _ = Outlet.objects.get_or_create(kind=kind, defaults={"name": name, "has_kitchen": kitchen})
        categories = {}
        for i, cat in enumerate(dict.fromkeys(m[0] for m in MENU)):
            categories[cat], _ = MenuCategory.objects.get_or_create(name=cat, defaults={"sort_order": i})
        for cat, name, name_am, price, sold_at, kitchen, breakfast in MENU:
            item, created = MenuItem.objects.get_or_create(name=name, defaults={
                "name_am": name_am, "category": categories[cat], "price": Decimal(price),
                "goes_to_kitchen": kitchen, "is_breakfast": breakfast,
            })
            if created:
                item.outlets.set([outlets[o] for o in sold_at] + ([outlets["room_service"]] if kitchen else []))

        for item, item_am, services in LAUNDRY:
            for service, price in services.items():
                LaundryPrice.objects.get_or_create(item=item, service=service, defaults={"item_am": item_am, "price": Decimal(price)})

        supplier, _ = Supplier.objects.get_or_create(name="Addis Fresh Supplies")
        stock = [
            ("Beef", "BEEF", "kg", "kitchen", "25", "8", "900"),
            ("Teff injera", "INJ", "piece", "kitchen", "120", "40", "25"),
            ("Coffee beans (Yirgacheffe)", "COF", "kg", "store", "10", "3", "1200"),
            ("St. George beer", "BEER-SG", "bottle", "bar", "96", "24", "70"),
            ("Ambo water 500ml", "AMBO", "bottle", "minibar", "60", "24", "30"),
            ("Shampoo sachet", "AMEN-SH", "piece", "amenities", "200", "50", "12"),
        ]
        for name, sku, unit, location, qty, reorder, cost in stock:
            InventoryItem.objects.get_or_create(sku=sku, defaults={
                "name": name, "unit": unit, "location": location, "stock": Decimal(qty), "reorder_level": Decimal(reorder),
                "unit_cost": Decimal(cost), "preferred_supplier": supplier,
            })
        recipes = [("Beef tibs", "BEEF", "0.250"), ("Special kitfo", "BEEF", "0.300"), ("St. George beer", "BEER-SG", "1")]
        for menu_name, sku, qty in recipes:
            RecipeLine.objects.get_or_create(
                menu_item=MenuItem.objects.get(name=menu_name), inventory_item=InventoryItem.objects.get(sku=sku),
                defaults={"quantity": Decimal(qty)},
            )

        for name, code in (("Expedia", "expedia"), ("Booking.com", "booking")):
            ChannelConnection.objects.get_or_create(code=code, defaults={"name": name})

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {Room.objects.count()} rooms, {MenuItem.objects.count()} menu items, "
            f"{Staff.objects.count()} staff. Log in as admin / admin12345, or any role with password vora12345."
        ))
