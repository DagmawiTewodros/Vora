from django.contrib import admin

from .models import HousekeepingTask


@admin.register(HousekeepingTask)
class HousekeepingTaskAdmin(admin.ModelAdmin):
    list_display = ["room", "task_type", "status", "assignee", "priority", "business_date"]
    list_filter = ["status", "task_type", "business_date"]
