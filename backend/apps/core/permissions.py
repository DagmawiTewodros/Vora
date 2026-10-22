from rest_framework.permissions import SAFE_METHODS, BasePermission

from .middleware import set_current_user
from .models import Role


def has_role(user, *roles):
    if not user or not user.is_authenticated:
        return False
    return user.is_manager or user.role in roles


class RolePermission(BasePermission):
    """Allows managers and admins, plus the roles listed on the view.

    Views set ``allowed_roles`` (any method) and optionally ``read_roles`` for
    roles that may only read.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        set_current_user(user)
        allowed = getattr(view, "allowed_roles", ())
        if has_role(user, *allowed):
            return True
        return request.method in SAFE_METHODS and user.role in getattr(view, "read_roles", ())


class ManagerOnly(BasePermission):
    def has_permission(self, request, view):
        set_current_user(request.user)
        return bool(request.user and request.user.is_authenticated and request.user.is_manager)


ALL_STAFF = tuple(Role.values)
