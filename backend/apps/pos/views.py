from django.db import transaction
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.models import HotelSettings, Role
from apps.core.permissions import ALL_STAFF, RolePermission

from . import services
from .models import BreakfastLog, MenuCategory, MenuItem, Order, OrderItem, Outlet
from .serializers import (
    BreakfastLogSerializer,
    CreateOrderSerializer,
    MenuCategorySerializer,
    MenuItemSerializer,
    NewItemSerializer,
    OfflineOrderSerializer,
    OrderItemSerializer,
    OrderSerializer,
    OutletSerializer,
    SettleSerializer,
)

POS_ROLES = (Role.WAITER, Role.CASHIER)


class OutletViewSet(viewsets.ModelViewSet):
    queryset = Outlet.objects.all()
    serializer_class = OutletSerializer
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF


class MenuCategoryViewSet(viewsets.ModelViewSet):
    queryset = MenuCategory.objects.all()
    serializer_class = MenuCategorySerializer
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.select_related("category").prefetch_related("outlets")
    serializer_class = MenuItemSerializer
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF
    filterset_fields = ["outlets", "category", "is_active", "is_breakfast"]
    search_fields = ["name", "name_am"]


def settle(order, data, user):
    kind = data["type"]
    if kind == "room":
        if not data.get("room"):
            raise ValidationError({"room": "Enter the room number."})
        return services.post_to_room(order, data["room"], user=user)
    if kind == "complimentary":
        if not user.is_manager:
            raise ValidationError("Only a manager can approve complimentary orders.")
        return services.settle_complimentary(order, reason=data.get("reason", ""), user=user)
    return services.settle_direct(
        order, payments=data.get("payments", []), user=user, customer_name=data.get("customer_name", ""),
        bill_to_name=data.get("bill_to_name", ""), bill_to_tin=data.get("bill_to_tin", ""),
    )


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Order.objects.select_related("outlet", "waiter", "folio__reservation__room").prefetch_related("items")
    serializer_class = OrderSerializer
    permission_classes = [RolePermission]
    allowed_roles = POS_ROLES
    read_roles = (Role.FRONT_DESK,)
    filterset_fields = ["outlet", "status", "settlement", "waiter", "business_date", "table"]
    search_fields = ["number", "table"]

    def _respond(self, order, code=status.HTTP_200_OK):
        return Response(OrderSerializer(self.get_queryset().get(pk=order.pk)).data, status=code)

    def create(self, request):
        data = CreateOrderSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = services.create_order(waiter=request.user, **data.validated_data)
        return self._respond(order, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def items(self, request, pk=None):
        data = NewItemSerializer(data=request.data.get("items", []), many=True)
        data.is_valid(raise_exception=True)
        services.add_items(self.get_object(), data.validated_data)
        return self._respond(self.get_object())

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/void")
    def void_item(self, request, pk=None, item_id=None):
        item = OrderItem.objects.get(pk=item_id, order=self.get_object())
        if item.kitchen_status != OrderItem.KitchenStatus.NEW and not request.user.is_manager:
            raise ValidationError("Items already sent to the kitchen need a manager to void.")
        services.void_item(item, request.data.get("reason", ""), request.user)
        return self._respond(self.get_object())

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        services.send_to_kitchen(self.get_object())
        return self._respond(self.get_object())

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        data = SettleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = settle(self.get_object(), data.validated_data, request.user)
        return self._respond(order)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        order = self.get_object()
        if order.items.exclude(kitchen_status=OrderItem.KitchenStatus.NEW).exists() and not request.user.is_manager:
            raise ValidationError("Orders already sent to the kitchen need a manager to void.")
        services.void_order(order, reason=request.data.get("reason", ""), user=request.user)
        return self._respond(order)

    @action(detail=False, methods=["post"])
    def sync(self, request):
        """Receive orders captured offline. Safe to resend: orders are matched on client_uuid."""
        results = []
        for raw in request.data.get("orders", []):
            data = OfflineOrderSerializer(data=raw)
            if not data.is_valid():
                results.append({"client_uuid": raw.get("client_uuid"), "ok": False, "errors": data.errors})
                continue
            values = dict(data.validated_data)
            settlement = values.pop("settlement", None)
            try:
                with transaction.atomic():
                    order = services.create_order(waiter=request.user, **values)
                    if settlement and order.status == Order.Status.OPEN:
                        order = settle(order, settlement, request.user)
                results.append({"client_uuid": str(values["client_uuid"]), "ok": True, "order": OrderSerializer(order).data})
            except ValidationError as exc:
                results.append({"client_uuid": str(values["client_uuid"]), "ok": False, "errors": exc.detail})
        return Response({"results": results})


@api_view(["GET"])
def kitchen_tickets(request):
    """Items waiting in the kitchen, oldest first."""
    items = (
        OrderItem.objects.select_related("order__outlet")
        .filter(kitchen_status__in=[OrderItem.KitchenStatus.SENT, OrderItem.KitchenStatus.READY], is_void=False)
        .order_by("sent_at")
    )
    outlet = request.query_params.get("outlet")
    if outlet:
        items = items.filter(order__outlet_id=outlet)
    tickets = {}
    for item in items:
        ticket = tickets.setdefault(item.order_id, {
            "order": item.order_id, "number": item.order.number, "outlet": item.order.outlet.name,
            "table": item.order.table, "sent_at": item.sent_at, "items": [],
        })
        ticket["items"].append(OrderItemSerializer(item).data)
    return Response(list(tickets.values()))


@api_view(["POST"])
def kitchen_item_status(request, item_id):
    item = OrderItem.objects.get(pk=item_id)
    new_status = request.data.get("kitchen_status")
    if new_status not in (OrderItem.KitchenStatus.READY, OrderItem.KitchenStatus.SERVED):
        raise ValidationError({"kitchen_status": "Use 'ready' or 'served'."})
    item.kitchen_status = new_status
    item.save(update_fields=["kitchen_status"])
    return Response(OrderItemSerializer(item).data)


class BreakfastLogViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = BreakfastLog.objects.select_related("reservation__guest", "reservation__room")
    serializer_class = BreakfastLogSerializer
    permission_classes = [RolePermission]
    allowed_roles = POS_ROLES + (Role.FRONT_DESK,)
    filterset_fields = ["business_date", "reservation"]

    def perform_create(self, serializer):
        reservation = serializer.validated_data["reservation"]
        if reservation.status != "checked_in":
            raise serializers.ValidationError("Breakfast can only be recorded for in-house guests.")
        day = HotelSettings.current_business_date()
        if BreakfastLog.objects.filter(reservation=reservation, business_date=day).exists():
            raise serializers.ValidationError("Breakfast is already recorded for this room today.")
        serializer.save(business_date=day, recorded_by=self.request.user)
