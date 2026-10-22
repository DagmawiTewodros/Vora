from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import HotelSettings
from apps.rooms.models import Room

from .models import HousekeepingTask

OPEN = (HousekeepingTask.Status.OPEN, HousekeepingTask.Status.IN_PROGRESS)


def _ensure_task(room, task_type, priority=2, notes=""):
    existing = HousekeepingTask.objects.filter(room=room, task_type=task_type, status__in=OPEN).first()
    if existing:
        return existing
    return HousekeepingTask.objects.create(
        room=room, task_type=task_type, priority=priority, notes=notes,
        business_date=HotelSettings.current_business_date(),
    )


def create_departure_task(room):
    return _ensure_task(room, HousekeepingTask.Type.DEPARTURE, priority=1)


def create_stayover_tasks():
    rooms = Room.objects.filter(status=Room.Status.OCCUPIED)
    return [_ensure_task(room, HousekeepingTask.Type.STAYOVER) for room in rooms]


@transaction.atomic
def start_task(task, user):
    if task.status != HousekeepingTask.Status.OPEN:
        raise ValidationError("Only open tasks can be started.")
    task.status = HousekeepingTask.Status.IN_PROGRESS
    task.started_at = timezone.now()
    task.assignee = task.assignee or user
    task.save()
    return task


@transaction.atomic
def complete_task(task, user, notes=""):
    task = HousekeepingTask.objects.select_for_update().get(pk=task.pk)
    if task.status not in OPEN:
        raise ValidationError("This task is already finished.")
    task.status = HousekeepingTask.Status.DONE
    task.done_at = timezone.now()
    task.done_by = user
    if notes:
        task.notes = notes
    task.save()

    room = Room.objects.select_for_update().get(pk=task.room_id)
    if task.task_type in (HousekeepingTask.Type.DEPARTURE, HousekeepingTask.Type.STAYOVER):
        room.housekeeping_status = Room.Housekeeping.CLEAN
        room.save()
        if task.task_type == HousekeepingTask.Type.DEPARTURE:
            _ensure_task(room, HousekeepingTask.Type.INSPECTION, priority=1)
    elif task.task_type == HousekeepingTask.Type.INSPECTION:
        room.housekeeping_status = Room.Housekeeping.INSPECTED
        room.save()
    return task


@transaction.atomic
def set_room_status(room, housekeeping_status, user=None):
    if housekeeping_status not in Room.Housekeeping.values:
        raise ValidationError({"housekeeping_status": "Unknown status."})
    room = Room.objects.select_for_update().get(pk=room.pk)
    room.housekeeping_status = housekeeping_status
    room.save()
    if housekeeping_status == Room.Housekeeping.DIRTY:
        task_type = HousekeepingTask.Type.STAYOVER if room.status == Room.Status.OCCUPIED else HousekeepingTask.Type.DEPARTURE
        _ensure_task(room, task_type)
    return room
