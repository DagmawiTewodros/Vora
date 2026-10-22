from rest_framework import serializers

from .ethiopian import format_ethiopian
from .models import AuditLog, ExchangeRate, HotelSettings, Staff


class StaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    pin = serializers.RegexField(r"^\d{4,6}$", write_only=True, required=False)
    has_pin = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "id", "username", "first_name", "last_name", "email", "phone", "role",
            "preferred_language", "is_active", "password", "pin", "has_pin", "last_login",
        ]
        read_only_fields = ["last_login"]

    def get_has_pin(self, obj):
        return bool(obj.pin_hash)

    def _apply_secrets(self, staff, password, pin):
        if password:
            staff.set_password(password)
        if pin:
            staff.set_pin(pin)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        pin = validated_data.pop("pin", None)
        staff = Staff(**validated_data)
        if not password:
            staff.set_unusable_password()
        self._apply_secrets(staff, password, pin)
        staff.save()
        return staff

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        pin = validated_data.pop("pin", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        self._apply_secrets(instance, password, pin)
        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    is_manager = serializers.BooleanField(read_only=True)

    class Meta:
        model = Staff
        fields = ["id", "username", "first_name", "last_name", "role", "preferred_language", "is_manager"]
        read_only_fields = ["id", "username", "role", "is_manager"]


class HotelSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelSettings
        exclude = ["id"]


class ExchangeRateSerializer(serializers.ModelSerializer):
    entered_by_name = serializers.StringRelatedField(source="entered_by", read_only=True)
    ethiopian_date = serializers.SerializerMethodField()

    class Meta:
        model = ExchangeRate
        fields = ["id", "date", "ethiopian_date", "usd_to_etb", "entered_by_name", "created_at"]

    def get_ethiopian_date(self, obj):
        return format_ethiopian(obj.date)


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.StringRelatedField(source="user")

    class Meta:
        model = AuditLog
        fields = ["id", "at", "user", "user_name", "action", "model", "object_id", "description", "before", "after"]


class PinLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    pin = serializers.CharField()
