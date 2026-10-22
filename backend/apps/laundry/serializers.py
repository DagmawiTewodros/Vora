from rest_framework import serializers

from .models import LaundryLine, LaundryPrice, LaundryTicket


class LaundryPriceSerializer(serializers.ModelSerializer):
    service_display = serializers.CharField(source="get_service_display", read_only=True)

    class Meta:
        model = LaundryPrice
        fields = "__all__"


class LaundryLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LaundryLine
        fields = ["id", "price", "description", "quantity", "unit_price", "line_total"]
        read_only_fields = ["description", "unit_price"]


class LaundryTicketSerializer(serializers.ModelSerializer):
    lines = LaundryLineSerializer(many=True)
    guest_name = serializers.CharField(source="reservation.guest.full_name", read_only=True)
    room_number = serializers.CharField(source="reservation.room.number", read_only=True, default=None)
    total = serializers.SerializerMethodField()

    class Meta:
        model = LaundryTicket
        fields = [
            "id", "number", "reservation", "guest_name", "room_number", "status", "express", "notes",
            "received_at", "delivered_at", "posted", "lines", "total",
        ]
        read_only_fields = ["number", "status", "received_at", "delivered_at", "posted"]

    def get_total(self, obj):
        subtotal = sum((line.line_total for line in obj.lines.all()), start=0)
        if obj.express:
            subtotal = subtotal * (1 + obj.express_surcharge_rate)
        return f"{subtotal:.2f}"
