from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, ExchangeRate, HotelSettings, Staff


@admin.register(Staff)
class StaffAdmin(UserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    fieldsets = UserAdmin.fieldsets + (("Hotel", {"fields": ("role", "phone", "preferred_language")}),)


@admin.register(HotelSettings)
class HotelSettingsAdmin(admin.ModelAdmin):
    pass


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ["date", "usd_to_etb", "entered_by"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["at", "user", "action", "model", "object_id", "description"]
    list_filter = ["action", "model"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
