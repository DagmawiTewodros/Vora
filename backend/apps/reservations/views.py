import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from apps.core.models import HotelSettings, Role
from apps.core.permissions import RolePermission
from apps.guests.models import Guest
from apps.rooms.models import Room, RoomType
from apps.rooms.serializers import RoomSerializer

from . import services
from .models import Group, Reservation
from .serializers import CheckInSerializer, GroupSerializer, ReservationSerializer, RoomMoveSerializer

FRONT_OFFICE = (Role.FRONT_DESK, Role.SALES, Role.REVENUE)


def parse_date(value, name):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError({name: "Use the YYYY-MM-DD format."})


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.select_related("guest", "room_type", "room", "stay__room").order_by("check_in", "id")
    serializer_class = ReservationSerializer
    permission_classes = [RolePermission]
    allowed_roles = FRONT_OFFICE
    read_roles = (Role.CASHIER, Role.HOUSEKEEPING, Role.WAITER, Role.LAUNDRY)
    filterset_fields = ["status", "source", "room_type", "room", "group", "guest", "check_in", "check_out"]
    search_fields = ["code", "guest__first_name", "guest__last_name", "guest__phone", "external_reference"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("from"):
            qs = qs.filter(check_out__gt=parse_date(params["from"], "from"))
        if params.get("to"):
            qs = qs.filter(check_in__lt=parse_date(params["to"], "to"))
        if params.get("active") == "true":
            qs = qs.filter(status__in=Reservation.ACTIVE_STATUSES)
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        new_guest = data.pop("new_guest", None)
        if new_guest:
            data["guest"] = Guest.objects.create(**new_guest)
        serializer.instance = services.create_reservation(user=self.request.user, **data)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("new_guest", None)
        serializer.instance = services.update_reservation(serializer.instance, user=self.request.user, **data)

    def destroy(self, request, *args, **kwargs):
        services.cancel_reservation(self.get_object(), reason=request.data.get("reason", ""), user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _respond(self, reservation):
        return Response(ReservationSerializer(Reservation.objects.get(pk=reservation.pk)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reservation = services.cancel_reservation(self.get_object(), reason=request.data.get("reason", ""), user=request.user)
        return self._respond(reservation)

    @action(detail=True, methods=["post"], url_path="no-show")
    def no_show(self, request, pk=None):
        reservation = services.cancel_reservation(
            self.get_object(), reason=request.data.get("reason", "No show"), user=request.user, no_show=True
        )
        return self._respond(reservation)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        reservation = self.get_object()
        if reservation.status != Reservation.Status.TENTATIVE:
            raise serializers.ValidationError("Only tentative reservations can be confirmed.")
        reservation.status = Reservation.Status.CONFIRMED
        reservation.save()
        return self._respond(reservation)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        data = CheckInSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        force = data.validated_data["force"] and request.user.is_manager
        reservation = services.check_in(
            self.get_object(),
            room=data.validated_data.get("room"),
            user=request.user,
            force=force,
            key_cards=data.validated_data["key_cards"],
        )
        return self._respond(reservation)

    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out(self, request, pk=None):
        return self._respond(services.check_out(self.get_object(), user=request.user))

    @action(detail=True, methods=["post"], url_path="prepare-check-out")
    def prepare_check_out(self, request, pk=None):
        """Post the remaining room nights so the final bill can be shown and paid."""
        services.post_final_room_charges(self.get_object(), user=request.user)
        return self._respond(self.get_object())

    @action(detail=True, methods=["post"], url_path="move-room")
    def move_room(self, request, pk=None):
        room = Room.objects.filter(pk=request.data.get("room")).first()
        if room is None:
            raise serializers.ValidationError({"room": "Choose a room."})
        reservation = services.move_room(self.get_object(), room, reason=request.data.get("reason", ""), user=request.user)
        return self._respond(reservation)

    @action(detail=True)
    def moves(self, request, pk=None):
        reservation = self.get_object()
        moves = reservation.stay.moves.all() if hasattr(reservation, "stay") else []
        return Response(RoomMoveSerializer(moves, many=True).data)

    @action(detail=True, url_path="free-rooms")
    def free_rooms(self, request, pk=None):
        reservation = self.get_object()
        start = max(reservation.check_in, HotelSettings.current_business_date())
        end = max(reservation.check_out, start + datetime.timedelta(days=1))
        room_type = reservation.room_type
        if request.query_params.get("room_type"):
            room_type = RoomType.objects.get(pk=request.query_params["room_type"])
        rooms = services.free_rooms(room_type, start, end, exclude=reservation)
        return Response(RoomSerializer(rooms, many=True, context={"in_house_map": {}}).data)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.order_by("-created_at")
    serializer_class = GroupSerializer
    permission_classes = [RolePermission]
    allowed_roles = FRONT_OFFICE
    search_fields = ["name", "company"]


@api_view(["GET"])
def availability(request):
    """Rooms left per type per night, plus a price quote for the stay."""
    start = parse_date(request.query_params.get("check_in"), "check_in")
    end = parse_date(request.query_params.get("check_out"), "check_out")
    if (end - start).days > 92:
        raise serializers.ValidationError("Ask for at most 92 nights at a time.")
    currency = request.query_params.get("currency", "ETB")
    grid = services.availability(start, end)
    result = []
    for room_type in RoomType.objects.all():
        nights = grid[room_type.pk]
        q = services.quote(room_type, start, end, currency)
        result.append({
            "room_type": room_type.pk,
            "name": room_type.name,
            "code": room_type.code,
            "capacity": room_type.capacity,
            "available": min(nights.values()) if nights else 0,
            "per_night": {n.isoformat(): c for n, c in nights.items()},
            "quote": {"total": q["total"], "currency": currency, "first_night": q["nights"][0]["price"] if q["nights"] else 0},
        })
    return Response(result)


@api_view(["GET"])
def front_desk_board(request):
    """Today's arrivals, departures and in-house guests."""
    today = HotelSettings.current_business_date()
    qs = Reservation.objects.select_related("guest", "room_type", "room", "stay__room")
    arrivals = qs.filter(check_in__lte=today, status__in=[Reservation.Status.TENTATIVE, Reservation.Status.CONFIRMED], check_out__gt=today)
    departures = qs.filter(check_out__lte=today, status=Reservation.Status.CHECKED_IN)
    in_house = qs.filter(status=Reservation.Status.CHECKED_IN)
    context = {"request": request}
    return Response({
        "business_date": today,
        "server_time": timezone.now(),
        "arrivals": ReservationSerializer(arrivals, many=True, context=context).data,
        "departures": ReservationSerializer(departures, many=True, context=context).data,
        "in_house": ReservationSerializer(in_house, many=True, context=context).data,
    })
