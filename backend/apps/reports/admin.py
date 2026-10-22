from django.contrib import admin

from .models import NightAudit


@admin.register(NightAudit)
class NightAuditAdmin(admin.ModelAdmin):
    list_display = ["business_date", "run_by", "run_at"]
    readonly_fields = ["business_date", "run_by", "run_at", "summary"]
