from rest_framework import serializers

from .models import Guest


class GuestSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    is_foreign = serializers.BooleanField(read_only=True)

    class Meta:
        model = Guest
        fields = "__all__"
