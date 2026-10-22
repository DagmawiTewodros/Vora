from rest_framework import serializers

from .models import RatePlan, Room, RoomType


class RoomTypeSerializer(serializers.ModelSerializer):
    room_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = RoomType
        fields = "__all__"


class RoomSerializer(serializers.ModelSerializer):
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    room_type_code = serializers.CharField(source="room_type.code", read_only=True)
    is_ready = serializers.BooleanField(read_only=True)
    current_guest = serializers.SerializerMethodField()
    current_reservation = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            "id", "number", "floor", "room_type", "room_type_name", "room_type_code", "status",
            "housekeeping_status", "out_of_order_reason", "notes", "is_active", "is_ready",
            "current_guest", "current_reservation",
        ]

    def _in_house(self, obj):
        mapping = self.context.get("in_house_map")
        if mapping is not None:
            return mapping.get(obj.pk)
        from apps.reservations.models import Reservation

        return Reservation.objects.select_related("guest").filter(room=obj, status=Reservation.Status.CHECKED_IN).first()

    def get_current_guest(self, obj):
        res = self._in_house(obj)
        return str(res.guest) if res else None

    def get_current_reservation(self, obj):
        res = self._in_house(obj)
        return res.pk if res else None


class RatePlanSerializer(serializers.ModelSerializer):
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)

    class Meta:
        model = RatePlan
        fields = "__all__"

    def validate(self, attrs):
        start = attrs.get("season_start", getattr(self.instance, "season_start", None))
        end = attrs.get("season_end", getattr(self.instance, "season_end", None))
        if start and end and end < start:
            raise serializers.ValidationError("Season end must be on or after season start.")
        return attrs
