import datetime

from django.contrib.auth.models import update_last_login
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .ethiopian import format_ethiopian
from .models import AuditLog, ExchangeRate, HotelSettings, Role, Staff
from .permissions import ALL_STAFF, ManagerOnly, RolePermission
from .serializers import (
    AuditLogSerializer,
    ExchangeRateSerializer,
    HotelSettingsSerializer,
    MeSerializer,
    PinLoginSerializer,
    StaffSerializer,
)


class AuditPagination(LimitOffsetPagination):
    default_limit = 200
    max_limit = 1000


class LoginThrottle(AnonRateThrottle):
    rate = "20/min"


def _tokens_for(staff):
    refresh = RefreshToken.for_user(staff)
    update_last_login(None, staff)
    return {"refresh": str(refresh), "access": str(refresh.access_token), "user": MeSerializer(staff).data}


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def password_login(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    staff = Staff.objects.filter(username=username, is_active=True).first()
    if not staff or not staff.check_password(password):
        return Response({"detail": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(_tokens_for(staff))


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def pin_login(request):
    """Fast PIN login for POS and front desk tills."""
    data = PinLoginSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    staff = Staff.objects.filter(username=data.validated_data["username"], is_active=True).first()
    if not staff or not staff.check_pin(data.validated_data["pin"]):
        return Response({"detail": "Invalid username or PIN."}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(_tokens_for(staff))


@api_view(["GET", "PATCH"])
def me(request):
    if request.method == "PATCH":
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    return Response(MeSerializer(request.user).data)


@api_view(["GET"])
def calendar_today(request):
    today = timezone.localdate()
    return Response({
        "gregorian": today.isoformat(),
        "ethiopian": format_ethiopian(today),
        "ethiopian_am": format_ethiopian(today, "am"),
    })


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.order_by("username")
    serializer_class = StaffSerializer
    permission_classes = [ManagerOnly]
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "first_name", "last_name"]

    def destroy(self, request, *args, **kwargs):
        # Staff are deactivated, never deleted, so the audit trail stays intact.
        staff = self.get_object()
        staff.is_active = False
        staff.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False)
    def roles(self, request):
        return Response([{"value": v, "label": label} for v, label in Role.choices])


class HotelSettingsViewSet(viewsets.ViewSet):
    permission_classes = [RolePermission]
    read_roles = ALL_STAFF

    def list(self, request):
        return Response(HotelSettingsSerializer(HotelSettings.load()).data)

    def partial_update(self, request, pk=None):
        serializer = HotelSettingsSerializer(HotelSettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.select_related("entered_by")
    serializer_class = ExchangeRateSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.CASHIER,)
    read_roles = ALL_STAFF

    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)

    @action(detail=False)
    def current(self, request):
        day = request.query_params.get("date")
        day = datetime.date.fromisoformat(day) if day else timezone.localdate()
        return Response({"date": day, "usd_to_etb": ExchangeRate.rate_for(day)})


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    permission_classes = [ManagerOnly]
    filterset_fields = ["user", "action", "model", "object_id"]
    search_fields = ["description", "model"]
    pagination_class = AuditPagination
