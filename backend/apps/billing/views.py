from django.db import IntegrityError, transaction
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import Role
from apps.core.permissions import RolePermission

from . import services
from .models import CashierShift, Charge, Folio, Payment
from .serializers import (
    CashierShiftSerializer,
    ChargeSerializer,
    FolioDetailSerializer,
    FolioSerializer,
    PaymentSerializer,
    PostChargeSerializer,
    TakePaymentSerializer,
)

BILLING_ROLES = (Role.FRONT_DESK, Role.CASHIER)


class FolioViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Folio.objects.select_related("reservation__room", "guest")
    permission_classes = [RolePermission]
    allowed_roles = BILLING_ROLES
    read_roles = (Role.WAITER, Role.LAUNDRY)
    filterset_fields = ["status", "reservation", "guest", "is_primary"]
    search_fields = ["number", "name", "invoice_number", "reservation__code", "reservation__room__number"]

    def get_serializer_class(self):
        return FolioDetailSerializer if self.action == "retrieve" else FolioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        room = self.request.query_params.get("room")
        if room:
            qs = qs.filter(reservation__room__number=room, reservation__status="checked_in")
        return qs

    def perform_update(self, serializer):
        if serializer.instance.status != Folio.Status.OPEN:
            raise serializers.ValidationError("Closed folios cannot be edited.")
        allowed = {"name", "bill_to_name", "bill_to_tin", "display_currency"}
        extra = set(serializer.validated_data) - allowed
        if extra:
            raise serializers.ValidationError(f"These fields cannot be changed: {', '.join(sorted(extra))}.")
        serializer.save()

    def _detail(self, folio):
        return Response(FolioDetailSerializer(Folio.objects.get(pk=folio.pk)).data)

    @action(detail=False, methods=["post"])
    def split(self, request):
        """Open an extra folio on a reservation (e.g. company pays room, guest pays extras)."""
        from apps.reservations.models import Reservation

        reservation = Reservation.objects.filter(pk=request.data.get("reservation")).first()
        if reservation is None:
            raise serializers.ValidationError({"reservation": "Choose a reservation."})
        folio = services.open_folio(
            reservation=reservation, name=request.data.get("name") or str(reservation.guest), is_primary=False
        )
        folio.bill_to_name = request.data.get("bill_to_name", "")
        folio.bill_to_tin = request.data.get("bill_to_tin", "")
        folio.save()
        return Response(FolioDetailSerializer(folio).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="walk-in")
    def walk_in(self, request):
        folio = services.open_folio(name=request.data.get("name") or "Walk-in customer")
        return Response(FolioDetailSerializer(folio).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def charges(self, request, pk=None):
        data = PostChargeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.post_charge(self.get_object(), user=request.user, **data.validated_data)
        return self._detail(self.get_object())

    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        data = TakePaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if data.validated_data["kind"] == Payment.Kind.REFUND and not request.user.is_manager:
            raise serializers.ValidationError("Only a manager can issue refunds.")
        services.take_payment(self.get_object(), user=request.user, **data.validated_data)
        return self._detail(self.get_object())

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        target = Folio.objects.filter(pk=request.data.get("to_folio")).first()
        if target is None:
            raise serializers.ValidationError({"to_folio": "Choose the folio to move charges to."})
        charges = Charge.objects.filter(folio=self.get_object(), pk__in=request.data.get("charges", []))
        services.transfer_charges(charges, target, user=request.user)
        return self._detail(self.get_object())

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        folio = services.close_folio(self.get_object(), user=request.user)
        return self._detail(folio)

    @action(detail=True)
    def invoice(self, request, pk=None):
        return Response(services.invoice_data(self.get_object()))


class ChargeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Charge.objects.select_related("folio", "posted_by")
    serializer_class = ChargeSerializer
    permission_classes = [RolePermission]
    allowed_roles = BILLING_ROLES
    filterset_fields = ["folio", "outlet", "business_date", "is_void"]

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        if not (request.user.is_manager or request.user.role == Role.CASHIER):
            raise serializers.ValidationError("Only a cashier or manager can void charges.")
        charge = services.void_charge(self.get_object(), reason=request.data.get("reason", ""), user=request.user)
        return Response(ChargeSerializer(charge).data)


class PaymentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Payment.objects.select_related("received_by")
    serializer_class = PaymentSerializer
    permission_classes = [RolePermission]
    allowed_roles = BILLING_ROLES
    filterset_fields = ["folio", "method", "business_date", "shift", "kind"]


class CashierShiftViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = CashierShift.objects.select_related("cashier")
    serializer_class = CashierShiftSerializer
    permission_classes = [RolePermission]
    allowed_roles = BILLING_ROLES + (Role.WAITER, Role.LAUNDRY)
    filterset_fields = ["cashier", "status"]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs if self.request.user.is_manager else qs.filter(cashier=self.request.user)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(cashier=self.request.user)
        except IntegrityError:
            raise serializers.ValidationError("You already have an open shift.")

    @action(detail=False)
    def current(self, request):
        shift = services.open_shift_for(request.user)
        return Response(CashierShiftSerializer(shift).data if shift else None)

    @action(detail=True)
    def summary(self, request, pk=None):
        return Response(services.shift_summary(self.get_object()))

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        shift = self.get_object()
        if shift.cashier_id != request.user.pk and not request.user.is_manager:
            raise serializers.ValidationError("You can only close your own shift.")
        if request.data.get("counted_cash_etb") in (None, ""):
            raise serializers.ValidationError({"counted_cash_etb": "Count the cash drawer before closing."})
        shift = services.close_shift(
            shift,
            counted_cash_etb=request.data["counted_cash_etb"],
            counted_cash_usd=request.data.get("counted_cash_usd") or 0,
            notes=request.data.get("notes", ""),
            user=request.user,
        )
        return Response(services.shift_summary(shift))
