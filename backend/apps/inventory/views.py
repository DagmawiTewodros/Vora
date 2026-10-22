from decimal import Decimal, InvalidOperation

from django.db.models import F
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import Role
from apps.core.permissions import RolePermission

from . import services
from .models import InventoryItem, PurchaseOrder, RecipeLine, StockMovement, Supplier
from .serializers import (
    InventoryItemSerializer,
    PurchaseOrderSerializer,
    RecipeLineSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)

STORE = (Role.STORE_KEEPER,)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.order_by("name")
    serializer_class = SupplierSerializer
    permission_classes = [RolePermission]
    allowed_roles = STORE
    search_fields = ["name"]


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.select_related("preferred_supplier")
    serializer_class = InventoryItemSerializer
    permission_classes = [RolePermission]
    allowed_roles = STORE
    read_roles = (Role.WAITER, Role.HOUSEKEEPING)
    filterset_fields = ["location", "is_active", "preferred_supplier"]
    search_fields = ["name", "sku"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("low") == "true":
            qs = qs.filter(stock__lte=F("reorder_level"))
        return qs

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        reason = request.data.get("reason")
        if reason not in (StockMovement.Reason.ISSUE, StockMovement.Reason.WASTE, StockMovement.Reason.PURCHASE):
            raise serializers.ValidationError({"reason": "Use issue, waste or purchase (use count for adjustments)."})
        try:
            change = abs(Decimal(str(request.data.get("quantity", 0))))
        except InvalidOperation:
            raise serializers.ValidationError({"quantity": "Enter a number."})
        if change == 0:
            raise serializers.ValidationError({"quantity": "Quantity must be more than zero."})
        if reason != StockMovement.Reason.PURCHASE:
            change = -change
        services.move_stock(
            self.get_object(), change, reason, note=request.data.get("note", ""), user=request.user,
            reference=request.data.get("reference", ""),
        )
        return Response(InventoryItemSerializer(InventoryItem.objects.get(pk=pk)).data)

    @action(detail=True, methods=["post"])
    def count(self, request, pk=None):
        if request.data.get("counted") in (None, ""):
            raise serializers.ValidationError({"counted": "Enter the counted quantity."})
        services.count_stock(self.get_object(), str(request.data["counted"]), user=request.user, note=request.data.get("note", ""))
        return Response(InventoryItemSerializer(InventoryItem.objects.get(pk=pk)).data)


class RecipeLineViewSet(viewsets.ModelViewSet):
    queryset = RecipeLine.objects.select_related("inventory_item")
    serializer_class = RecipeLineSerializer
    permission_classes = [RolePermission]
    allowed_roles = STORE
    filterset_fields = ["menu_item", "inventory_item"]


class StockMovementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = StockMovement.objects.select_related("item", "user")
    serializer_class = StockMovementSerializer
    permission_classes = [RolePermission]
    allowed_roles = STORE
    filterset_fields = ["item", "reason"]


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related("supplier").prefetch_related("lines__item")
    serializer_class = PurchaseOrderSerializer
    permission_classes = [RolePermission]
    allowed_roles = STORE
    filterset_fields = ["status", "supplier"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        po = self.get_object()
        if po.status != PurchaseOrder.Status.DRAFT:
            raise serializers.ValidationError("Only drafts can be deleted; cancel the order instead.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="mark-ordered")
    def mark_ordered(self, request, pk=None):
        po = self.get_object()
        if po.status != PurchaseOrder.Status.DRAFT:
            raise serializers.ValidationError("Only drafts can be sent to the supplier.")
        po.status = PurchaseOrder.Status.ORDERED
        po.save()
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        po = services.receive_purchase_order(self.get_object(), received=request.data.get("received"), user=request.user)
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        po = self.get_object()
        if po.status == PurchaseOrder.Status.RECEIVED:
            raise serializers.ValidationError("Received orders cannot be cancelled.")
        po.status = PurchaseOrder.Status.CANCELLED
        po.save()
        return Response(PurchaseOrderSerializer(po).data)
