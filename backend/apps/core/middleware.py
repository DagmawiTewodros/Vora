import threading

_state = threading.local()


def get_current_user():
    user = getattr(_state, "user", None)
    return user if user is not None and user.is_authenticated else None


def set_current_user(user):
    _state.user = user


class CurrentUserMiddleware:
    """Remembers the request user so audit signals can record who made a change.

    DRF authenticates JWT users after middleware runs, so views also call
    set_current_user (see apps.core.permissions.AuditUserMixin).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)
