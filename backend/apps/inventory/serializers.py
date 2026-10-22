from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.billing.services import next_number

from .models import InventoryItem, PurchaseOrder, PurchaseOrderLine, RecipeLine, StockMovement, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class InventoryItemSerializer(serializers.ModelSerializer):
    needs_reorder = serializers.BooleanField(read_only=True)
    supplier_name = serializers.CharField(source="preferred_supplier.name", read_only=True, default=None)

    class Meta:
        model = InventoryItem
        fields = "__all__"
        read_only_fields = ["stock"]


class RecipeLineSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    unit = serializers.CharField(source="inventory_item.unit", read_only=True)

    class Meta:
        model = RecipeLine
        fields = "__all__"


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    user_name = serializers.StringRelatedField(source="user", read_only=True)

    class Meta:
        model = StockMovement
        fields = "__all__"
        read_only_fields = ["stock_after", "user", "at"]


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = ["id", "item", "item_name", "quantity", "unit_cost", "received_quantity"]
        read_only_fields = ["received_quantity"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "number", "supplier", "supplier_name", "status", "expected_date", "notes", "created_at",
            "received_at", "lines", "total",
        ]
        read_only_fields = ["number", "status", "created_at", "received_at"]

    def get_total(self, obj):
        return f"{sum((line.quantity * line.unit_cost for line in obj.lines.all()), start=0):.2f}"

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        if not lines:
            raise serializers.ValidationError({"lines": "Add at least one line."})
        year = timezone.localdate().year
        po = PurchaseOrder.objects.create(number=f"PO{year}-{next_number(f'po-{year}'):05d}", **validated_data)
        for line in lines:
            PurchaseOrderLine.objects.create(order=po, **line)
        return po

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status != PurchaseOrder.Status.DRAFT:
            raise serializers.ValidationError("Only draft purchase orders can be edited.")
        lines = validated_data.pop("lines", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                PurchaseOrderLine.objects.create(order=instance, **line)
        return instance
