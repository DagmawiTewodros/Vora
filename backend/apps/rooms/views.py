from django.db.models import Count, Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import Role
from apps.core.permissions import ALL_STAFF, RolePermission

from .models import RatePlan, Room, RoomType
from .serializers import RatePlanSerializer, RoomSerializer, RoomTypeSerializer


class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.annotate(room_count=Count("rooms", filter=Q(rooms__is_active=True)))
    serializer_class = RoomTypeSerializer
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("room_type")
    serializer_class = RoomSerializer
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF
    filterset_fields = ["room_type", "status", "housekeeping_status", "floor", "is_active"]
    search_fields = ["number"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "list":
            from apps.reservations.models import Reservation

            in_house = Reservation.objects.select_related("guest").filter(status=Reservation.Status.CHECKED_IN)
            context["in_house_map"] = {r.room_id: r for r in in_house}
        return context

    @action(detail=True, methods=["post"], url_path="out-of-order")
    def out_of_order(self, request, pk=None):
        room = self.get_object()
        if room.status == Room.Status.OCCUPIED:
            raise serializers.ValidationError("An occupied room cannot be put out of order.")
        reason = request.data.get("reason", "")
        if not reason:
            raise serializers.ValidationError({"reason": "A reason is required."})
        room.status = Room.Status.OUT_OF_ORDER
        room.out_of_order_reason = reason
        room.save()
        return Response(RoomSerializer(room).data)

    @action(detail=True, methods=["post"], url_path="return-to-service")
    def return_to_service(self, request, pk=None):
        room = self.get_object()
        if room.status == Room.Status.OUT_OF_ORDER:
            room.status = Room.Status.VACANT
            room.housekeeping_status = Room.Housekeeping.DIRTY
            room.out_of_order_reason = ""
            room.save()
        return Response(RoomSerializer(room).data)


class RatePlanViewSet(viewsets.ModelViewSet):
    queryset = RatePlan.objects.select_related("room_type")
    serializer_class = RatePlanSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.REVENUE,)
    read_roles = ALL_STAFF
    filterset_fields = ["room_type", "is_active", "is_public", "is_corporate"]
