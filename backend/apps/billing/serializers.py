from decimal import Decimal

from rest_framework import serializers

from .models import CashierShift, Charge, Folio, Outlet, Payment, PaymentMethod
from .services import folio_totals


class ChargeSerializer(serializers.ModelSerializer):
    outlet_display = serializers.CharField(source="get_outlet_display", read_only=True)
    posted_by_name = serializers.StringRelatedField(source="posted_by", read_only=True)

    class Meta:
        model = Charge
        fields = [
            "id", "folio", "outlet", "outlet_display", "description", "quantity", "unit_price", "net_amount",
            "service_charge", "vat", "total", "business_date", "room_night", "original_currency", "original_amount",
            "exchange_rate", "source_type", "source_id", "posted_by_name", "posted_at", "is_void", "void_reason",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    received_by_name = serializers.StringRelatedField(source="received_by", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "folio", "kind", "method", "method_display", "currency", "amount", "exchange_rate", "amount_etb",
            "reference", "shift", "business_date", "received_by_name", "received_at",
        ]


class FolioSerializer(serializers.ModelSerializer):
    totals = serializers.SerializerMethodField()
    reservation_code = serializers.CharField(source="reservation.code", read_only=True, default=None)
    room_number = serializers.CharField(source="reservation.room.number", read_only=True, default=None)

    class Meta:
        model = Folio
        fields = [
            "id", "number", "reservation", "reservation_code", "room_number", "guest", "name", "is_primary",
            "display_currency", "bill_to_name", "bill_to_tin", "status", "opened_at", "closed_at",
            "invoice_number", "fiscal_receipt_number", "totals",
        ]
        read_only_fields = ["number", "status", "opened_at", "closed_at", "invoice_number", "fiscal_receipt_number"]

    def get_totals(self, obj):
        return {k: str(v) for k, v in folio_totals(obj).items()}


class FolioDetailSerializer(FolioSerializer):
    charges = ChargeSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta(FolioSerializer.Meta):
        fields = FolioSerializer.Meta.fields + ["charges", "payments"]


class PostChargeSerializer(serializers.Serializer):
    outlet = serializers.ChoiceField(choices=Outlet.choices)
    description = serializers.CharField(max_length=200)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2, default=1)
    currency = serializers.ChoiceField(choices=["ETB", "USD"], default="ETB")
    apply_service_charge = serializers.BooleanField(default=True)
    apply_vat = serializers.BooleanField(default=True)


class TakePaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.ChoiceField(choices=["ETB", "USD"], default="ETB")
    reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    kind = serializers.ChoiceField(choices=Payment.Kind.choices, default=Payment.Kind.PAYMENT)


class CashierShiftSerializer(serializers.ModelSerializer):
    cashier_name = serializers.StringRelatedField(source="cashier", read_only=True)

    class Meta:
        model = CashierShift
        fields = [
            "id", "cashier", "cashier_name", "status", "opened_at", "closed_at", "opening_float",
            "counted_cash_etb", "counted_cash_usd", "notes",
        ]
        read_only_fields = ["cashier", "status", "opened_at", "closed_at", "counted_cash_etb", "counted_cash_usd"]
