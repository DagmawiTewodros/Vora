from django.contrib import admin

from .models import ChannelConnection, ChannelSyncLog


@admin.register(ChannelConnection)
class ChannelConnectionAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "stop_sell", "rate_markup_pct", "last_push_at"]


@admin.register(ChannelSyncLog)
class ChannelSyncLogAdmin(admin.ModelAdmin):
    list_display = ["at", "channel", "direction", "ok", "message"]
    list_filter = ["channel", "direction", "ok"]
