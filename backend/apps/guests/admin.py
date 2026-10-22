from django.contrib import admin

from .models import Guest


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "phone", "nationality", "id_type", "id_number", "vip"]
    search_fields = ["first_name", "last_name", "phone", "id_number"]
