from django.apps import AppConfig, apps

AUDITED_MODELS = [
    "core.Staff", "core.HotelSettings", "core.ExchangeRate",
    "rooms.RoomType", "rooms.Room", "rooms.RatePlan",
    "guests.Guest",
    "reservations.Reservation", "reservations.Stay",
    "billing.Folio", "billing.Charge", "billing.Payment", "billing.CashierShift",
    "pos.MenuItem", "pos.Order",
    "laundry.LaundryPrice", "laundry.LaundryTicket",
    "inventory.InventoryItem", "inventory.PurchaseOrder",
    "distribution.ChannelConnection",
]


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from . import audit

        audit.register(*(apps.get_model(label) for label in AUDITED_MODELS))
