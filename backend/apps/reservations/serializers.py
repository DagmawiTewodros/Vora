from rest_framework import serializers

from apps.guests.models import Guest
from apps.guests.serializers import GuestSerializer
from apps.rooms.models import Room

from .models import Group, Reservation, RoomMove, Stay


class GroupSerializer(serializers.ModelSerializer):
    reservation_count = serializers.IntegerField(source="reservations.count", read_only=True)

    class Meta:
        model = Group
        fields = "__all__"


class StaySerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)

    class Meta:
        model = Stay
        fields = ["room", "room_number", "checked_in_at", "checked_out_at", "key_cards_issued"]


class RoomMoveSerializer(serializers.ModelSerializer):
    from_room_number = serializers.CharField(source="from_room.number", read_only=True)
    to_room_number = serializers.CharField(source="to_room.number", read_only=True)

    class Meta:
        model = RoomMove
        fields = ["from_room_number", "to_room_number", "reason", "moved_at"]


class ReservationSerializer(serializers.ModelSerializer):
    guest_detail = GuestSerializer(source="guest", read_only=True)
    new_guest = GuestSerializer(write_only=True, required=False)
    guest = serializers.PrimaryKeyRelatedField(queryset=Guest.objects.all(), required=False)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    room_number = serializers.CharField(source="room.number", read_only=True, default=None)
    nights = serializers.IntegerField(read_only=True)
    nightly_rate = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    stay = StaySerializer(read_only=True)
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id", "code", "guest", "guest_detail", "new_guest", "group", "room_type", "room_type_name", "room",
            "room_number", "rate_plan", "check_in", "check_out", "nights", "adults", "children", "source", "channel",
            "external_reference", "status", "currency", "nightly_rate", "breakfast_included", "deposit_required",
            "special_requests", "created_at", "cancelled_at", "cancellation_reason", "stay", "balance",
        ]
        read_only_fields = ["code", "status", "created_at", "cancelled_at", "cancellation_reason"]

    def get_balance(self, obj):
        from apps.billing.services import reservation_balance

        return str(reservation_balance(obj))

    def validate(self, attrs):
        if self.instance is None and not attrs.get("guest") and not attrs.get("new_guest"):
            raise serializers.ValidationError({"guest": "Choose a guest or enter a new one."})
        return attrs


class CheckInSerializer(serializers.Serializer):
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all(), required=False)
    force = serializers.BooleanField(default=False)
    key_cards = serializers.IntegerField(default=1, min_value=0, max_value=5)
