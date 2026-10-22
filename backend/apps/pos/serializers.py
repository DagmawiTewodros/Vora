from decimal import Decimal

from rest_framework import serializers

from apps.billing.models import PaymentMethod

from .models import BreakfastLog, MenuCategory, MenuItem, Order, OrderItem, Outlet


class OutletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = "__all__"


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = "__all__"


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)

    class Meta:
        model = MenuItem
        fields = "__all__"


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "menu_item", "name", "quantity", "unit_price", "notes", "kitchen_status", "sent_at", "is_void", "line_total"]
        read_only_fields = ["name", "unit_price", "kitchen_status", "sent_at", "is_void"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    outlet_name = serializers.CharField(source="outlet.name", read_only=True)
    waiter_name = serializers.StringRelatedField(source="waiter", read_only=True)
    subtotal = serializers.SerializerMethodField()
    folio_number = serializers.CharField(source="folio.number", read_only=True, default=None)
    room_number = serializers.CharField(source="folio.reservation.room.number", read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            "id", "number", "client_uuid", "outlet", "outlet_name", "table", "covers", "waiter", "waiter_name", "status",
            "settlement", "folio", "folio_number", "room_number", "notes", "business_date", "created_at", "settled_at",
            "void_reason", "items", "subtotal",
        ]
        read_only_fields = ["number", "waiter", "status", "settlement", "folio", "business_date", "settled_at", "void_reason"]

    def get_subtotal(self, obj):
        return str(sum((i.line_total for i in obj.items.all() if not i.is_void), start=0))


class NewItemSerializer(serializers.Serializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    quantity = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class CreateOrderSerializer(serializers.Serializer):
    outlet = serializers.PrimaryKeyRelatedField(queryset=Outlet.objects.filter(is_active=True))
    table = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    covers = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    items = NewItemSerializer(many=True, required=False, default=list)


class PaymentLineSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    currency = serializers.ChoiceField(choices=["ETB", "USD"], default="ETB")
    reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class SettleSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["room", "direct", "complimentary"])
    room = serializers.CharField(required=False, allow_blank=True)
    payments = PaymentLineSerializer(many=True, required=False, default=list)
    customer_name = serializers.CharField(required=False, allow_blank=True, default="")
    bill_to_name = serializers.CharField(required=False, allow_blank=True, default="")
    bill_to_tin = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class OfflineOrderSerializer(CreateOrderSerializer):
    client_uuid = serializers.UUIDField()
    settlement = SettleSerializer(required=False, allow_null=True)


class BreakfastLogSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source="reservation.guest.full_name", read_only=True)
    room_number = serializers.CharField(source="reservation.room.number", read_only=True, default=None)

    class Meta:
        model = BreakfastLog
        fields = ["id", "reservation", "guest_name", "room_number", "business_date", "covers", "recorded_at"]
        read_only_fields = ["business_date", "recorded_at"]
