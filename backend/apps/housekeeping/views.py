from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import HotelSettings, Role
from apps.core.permissions import RolePermission
from apps.rooms.models import Room
from apps.rooms.serializers import RoomSerializer

from . import services
from .models import HousekeepingTask
from .serializers import HousekeepingTaskSerializer


class HousekeepingTaskViewSet(viewsets.ModelViewSet):
    queryset = HousekeepingTask.objects.select_related("room", "assignee")
    serializer_class = HousekeepingTaskSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.HOUSEKEEPING, Role.FRONT_DESK)
    filterset_fields = ["status", "task_type", "assignee", "room", "business_date"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("mine") == "true":
            qs = qs.filter(assignee=self.request.user)
        if self.request.query_params.get("open") == "true":
            qs = qs.filter(status__in=services.OPEN)
        return qs

    def perform_create(self, serializer):
        serializer.save(business_date=HotelSettings.current_business_date())

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return Response(HousekeepingTaskSerializer(services.start_task(self.get_object(), request.user)).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = services.complete_task(self.get_object(), request.user, notes=request.data.get("notes", ""))
        return Response(HousekeepingTaskSerializer(task).data)


class RoomStatusViewSet(viewsets.GenericViewSet):
    """Room status board shared by front desk and housekeeping."""

    queryset = Room.objects.filter(is_active=True).select_related("room_type")
    permission_classes = [RolePermission]
    allowed_roles = (Role.HOUSEKEEPING, Role.FRONT_DESK)

    def list(self, request):
        rooms = self.get_queryset()
        from apps.reservations.models import Reservation

        in_house = {r.room_id: r for r in Reservation.objects.select_related("guest").filter(status="checked_in")}
        counts = rooms.values("housekeeping_status").annotate(n=Count("id"))
        return Response({
            "rooms": RoomSerializer(rooms, many=True, context={"in_house_map": in_house}).data,
            "counts": {c["housekeeping_status"]: c["n"] for c in counts},
        })

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        room = services.set_room_status(self.get_object(), request.data.get("housekeeping_status"), request.user)
        return Response(RoomSerializer(room).data)
