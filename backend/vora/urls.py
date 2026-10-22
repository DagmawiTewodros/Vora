from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


api = [
    path("", include("apps.core.urls")),
    path("", include("apps.rooms.urls")),
    path("", include("apps.guests.urls")),
    path("", include("apps.reservations.urls")),
    path("", include("apps.billing.urls")),
    path("", include("apps.housekeeping.urls")),
    path("", include("apps.pos.urls")),
    path("", include("apps.laundry.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.reports.urls")),
    path("", include("apps.distribution.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
    path("health/", health),
]

admin.site.site_header = "Vora Addis HMS"
admin.site.site_title = "Vora Addis HMS"
