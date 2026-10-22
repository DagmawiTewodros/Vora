from django.contrib import admin

from .models import Group, Reservation, RoomMove, Stay


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ["code", "guest", "room_type", "room", "check_in", "check_out", "status", "source"]
    list_filter = ["status", "source", "room_type"]
    search_fields = ["code", "guest__first_name", "guest__last_name", "external_reference"]


admin.site.register(Group)
admin.site.register(Stay)
admin.site.register(RoomMove)
