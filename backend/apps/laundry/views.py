from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import Role
from apps.core.permissions import ALL_STAFF, RolePermission

from . import services
from .models import LaundryPrice, LaundryTicket
from .serializers import LaundryPriceSerializer, LaundryTicketSerializer


class LaundryPriceViewSet(viewsets.ModelViewSet):
    queryset = LaundryPrice.objects.all()
    serializer_class = LaundryPriceSerializer
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF
    filterset_fields = ["service", "is_active"]


class LaundryTicketViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = LaundryTicket.objects.select_related("reservation__guest", "reservation__room").prefetch_related("lines")
    serializer_class = LaundryTicketSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.LAUNDRY, Role.FRONT_DESK, Role.HOUSEKEEPING)
    filterset_fields = ["status", "reservation", "posted"]
    search_fields = ["number", "reservation__room__number", "reservation__guest__last_name"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ticket = services.create_ticket(
            reservation=data["reservation"], lines=data["lines"], express=data.get("express", False),
            notes=data.get("notes", ""), user=request.user,
        )
        return Response(LaundryTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        return Response(LaundryTicketSerializer(services.advance(self.get_object(), request.user)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(LaundryTicketSerializer(services.cancel(self.get_object(), request.user)).data)
