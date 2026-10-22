import datetime
import hmac

from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.core.models import Role
from apps.core.permissions import RolePermission
from apps.guests.models import Guest
from apps.reservations import services as booking
from apps.reservations.models import Reservation
from apps.rooms.models import RoomType

from . import services
from .models import ChannelConnection, ChannelSyncLog


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelConnection
        fields = "__all__"
        extra_kwargs = {"webhook_secret": {"write_only": True}}


class SyncLogSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)

    class Meta:
        model = ChannelSyncLog
        exclude = ["payload"]


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = ChannelConnection.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.REVENUE,)

    @action(detail=True, methods=["post"])
    def push(self, request, pk=None):
        payload = services.push_availability(self.get_object(), days=int(request.data.get("days", 30)))
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="stop-sell")
    def stop_sell(self, request, pk=None):
        channel = self.get_object()
        channel.stop_sell = bool(request.data.get("stop_sell", True))
        channel.save()
        services.push_availability(channel)
        return Response(ChannelSerializer(channel).data)


class SyncLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = ChannelSyncLog.objects.select_related("channel")
    serializer_class = SyncLogSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.REVENUE,)
    filterset_fields = ["channel", "direction", "ok"]


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def ota_webhook(request, code):
    """Inbound reservations from an OTA / channel manager, signed with X-Vora-Secret."""
    channel = ChannelConnection.objects.filter(code=code, is_active=True).first()
    secret = request.headers.get("X-Vora-Secret", "")
    if channel is None or not hmac.compare_digest(secret, channel.webhook_secret):
        return Response({"detail": "Unknown channel or bad secret."}, status=status.HTTP_403_FORBIDDEN)
    try:
        reservation = services.receive_booking(channel, request.data)
    except ValidationError as exc:
        ChannelSyncLog.objects.create(channel=channel, direction="booking", ok=False, message=str(exc.detail)[:255], payload=request.data)
        raise
    return Response({"reservation": reservation.code if reservation else None, "status": reservation.status if reservation else "unknown"})


class PublicThrottle(AnonRateThrottle):
    rate = "60/min"


def _dates(params):
    try:
        start = datetime.date.fromisoformat(params.get("check_in", ""))
        end = datetime.date.fromisoformat(params.get("check_out", ""))
    except ValueError:
        raise ValidationError("Pass check_in and check_out as YYYY-MM-DD.")
    if start < timezone.localdate():
        raise ValidationError("Check-in cannot be in the past.")
    if not 1 <= (end - start).days <= 30:
        raise ValidationError("Stays must be between 1 and 30 nights.")
    return start, end


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_availability(request):
    """Booking engine for the hotel website."""
    start, end = _dates(request.query_params)
    currency = "USD" if request.query_params.get("currency") == "USD" else "ETB"
    grid = booking.availability(start, end)
    offers = []
    for room_type in RoomType.objects.all():
        left = min(grid[room_type.pk].values())
        if left < 1:
            continue
        q = booking.quote(room_type, start, end, currency, public_only=True)
        offers.append({
            "room_type": room_type.code, "name": room_type.name, "description": room_type.description,
            "capacity": room_type.capacity, "amenities": room_type.amenities, "rooms_left": min(left, 5),
            "currency": currency, "total": str(q["total"]), "nights": len(q["nights"]),
            "breakfast_included": bool(q["rate_plan"] and q["rate_plan"].breakfast_included),
        })
    return Response({"check_in": start, "check_out": end, "offers": offers})


class PublicBookingSerializer(serializers.Serializer):
    room_type = serializers.SlugRelatedField(slug_field="code", queryset=RoomType.objects.all())
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    adults = serializers.IntegerField(min_value=1, max_value=6, default=1)
    children = serializers.IntegerField(min_value=0, max_value=6, default=0)
    currency = serializers.ChoiceField(choices=["ETB", "USD"], default="ETB")
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    nationality = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    special_requests = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_book(request):
    data = PublicBookingSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    d = data.validated_data
    _dates({"check_in": d["check_in"].isoformat(), "check_out": d["check_out"].isoformat()})
    guest = Guest.objects.create(
        first_name=d["first_name"], last_name=d["last_name"], email=d["email"], phone=d["phone"], nationality=d["nationality"]
    )
    q = booking.quote(d["room_type"], d["check_in"], d["check_out"], d["currency"], public_only=True)
    reservation = booking.create_reservation(
        guest=guest, room_type=d["room_type"], check_in=d["check_in"], check_out=d["check_out"],
        adults=d["adults"], children=d["children"], source=Reservation.Source.DIRECT,
        status=Reservation.Status.TENTATIVE, currency=d["currency"], rate_plan=q["rate_plan"],
        special_requests=d["special_requests"],
    )
    return Response(
        {"reservation": reservation.code, "status": reservation.status, "total": str(q["total"]), "currency": d["currency"]},
        status=status.HTTP_201_CREATED,
    )
