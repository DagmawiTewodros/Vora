from rest_framework import viewsets

from apps.core.models import Role
from apps.core.permissions import RolePermission

from .models import Guest
from .serializers import GuestSerializer


class GuestViewSet(viewsets.ModelViewSet):
    queryset = Guest.objects.all()
    serializer_class = GuestSerializer
    permission_classes = [RolePermission]
    allowed_roles = (Role.FRONT_DESK, Role.SALES, Role.CASHIER)
    read_roles = (Role.WAITER, Role.LAUNDRY, Role.REVENUE)
    search_fields = ["first_name", "last_name", "phone", "email", "id_number", "company"]
    filterset_fields = ["nationality", "vip"]
