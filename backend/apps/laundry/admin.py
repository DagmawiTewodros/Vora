from django.contrib import admin

from .models import LaundryLine, LaundryPrice, LaundryTicket


class LaundryLineInline(admin.TabularInline):
    model = LaundryLine
    extra = 0


@admin.register(LaundryTicket)
class LaundryTicketAdmin(admin.ModelAdmin):
    list_display = ["number", "reservation", "status", "express", "posted", "received_at"]
    list_filter = ["status", "express"]
    inlines = [LaundryLineInline]


@admin.register(LaundryPrice)
class LaundryPriceAdmin(admin.ModelAdmin):
    list_display = ["item", "service", "price", "is_active"]
