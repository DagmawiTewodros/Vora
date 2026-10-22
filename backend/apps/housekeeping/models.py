from django.conf import settings
from django.db import models


class HousekeepingTask(models.Model):
    class Type(models.TextChoices):
        DEPARTURE = "departure", "Departure clean"
        STAYOVER = "stayover", "Stay-over clean"
        INSPECTION = "inspection", "Inspection"
        TURNDOWN = "turndown", "Turndown"
        MAINTENANCE = "maintenance", "Maintenance"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    room = models.ForeignKey("rooms.Room", on_delete=models.CASCADE, related_name="housekeeping_tasks")
    task_type = models.CharField(max_length=15, choices=Type.choices)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="housekeeping_tasks"
    )
    priority = models.PositiveSmallIntegerField(default=2, help_text="1 = urgent (arrival waiting), 3 = low.")
    business_date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["status", "priority", "room__number"]

    def __str__(self):
        return f"{self.get_task_type_display()} – room {self.room.number}"
