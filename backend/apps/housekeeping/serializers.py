from rest_framework import serializers

from .models import HousekeepingTask


class HousekeepingTaskSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)
    room_floor = serializers.IntegerField(source="room.floor", read_only=True)
    room_status = serializers.CharField(source="room.status", read_only=True)
    housekeeping_status = serializers.CharField(source="room.housekeeping_status", read_only=True)
    assignee_name = serializers.StringRelatedField(source="assignee", read_only=True)
    task_type_display = serializers.CharField(source="get_task_type_display", read_only=True)

    class Meta:
        model = HousekeepingTask
        fields = [
            "id", "room", "room_number", "room_floor", "room_status", "housekeeping_status", "task_type",
            "task_type_display", "status", "assignee", "assignee_name", "priority", "business_date", "notes",
            "created_at", "started_at", "done_at",
        ]
        read_only_fields = ["status", "business_date", "created_at", "started_at", "done_at"]
