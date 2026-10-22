import datetime

from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.models import HotelSettings, Role
from apps.core.permissions import ManagerOnly

from . import services
from .models import NightAudit


def _date(request, name, default):
    value = request.query_params.get(name)
    if not value:
        return default
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise serializers.ValidationError({name: "Use the YYYY-MM-DD format."})




@api_view(["GET"])
@permission_classes([ManagerOnly])
def daily(request):
    day = _date(request, "date", HotelSettings.current_business_date())
    return Response(services.day_report(day))


@api_view(["GET"])
@permission_classes([ManagerOnly])
def summary(request):
    today = HotelSettings.current_business_date()
    end = _date(request, "end", today)
    start = _date(request, "start", end - datetime.timedelta(days=6))
    return Response(services.range_report(start, end))


@api_view(["GET"])
def guest_register(request):
    if not (request.user.is_manager or request.user.role == Role.FRONT_DESK):
        raise serializers.ValidationError("Only front desk and managers can print the guest register.")
    day = _date(request, "date", HotelSettings.current_business_date())
    return Response({"date": day, "printed_at": timezone.now(), "hotel": HotelSettings.load().name,
                     "guests": services.guest_register(day)})


@api_view(["GET"])
def breakfast(request):
    day = _date(request, "date", HotelSettings.current_business_date())
    return Response(services.breakfast_report(day))


@api_view(["POST"])
@permission_classes([ManagerOnly])
def run_night_audit(request):
    audit = services.run_night_audit(user=request.user)
    return Response({"business_date": audit.business_date, "run_at": audit.run_at, "summary": audit.summary})


class NightAuditViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = NightAudit.objects.select_related("run_by")
    permission_classes = [ManagerOnly]

    class _Serializer(serializers.ModelSerializer):
        run_by_name = serializers.StringRelatedField(source="run_by")

        class Meta:
            model = NightAudit
            fields = ["id", "business_date", "run_by_name", "run_at", "summary"]

    serializer_class = _Serializer
