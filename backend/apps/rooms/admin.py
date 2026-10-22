from django.contrib import admin

from .models import RatePlan, Room, RoomType


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "capacity", "base_rate_etb", "base_rate_usd"]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["number", "floor", "room_type", "status", "housekeeping_status", "is_active"]
    list_filter = ["room_type", "status", "housekeeping_status", "floor"]


@admin.register(RatePlan)
class RatePlanAdmin(admin.ModelAdmin):
    list_display = ["name", "room_type", "price_etb", "price_usd", "breakfast_included", "season_start", "season_end", "is_active"]
    list_filter = ["room_type", "is_active"]
