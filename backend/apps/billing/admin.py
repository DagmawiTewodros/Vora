from django.contrib import admin

from .models import CashierShift, Charge, Folio, Payment


class ChargeInline(admin.TabularInline):
    model = Charge
    extra = 0
    can_delete = False
    fields = ["business_date", "outlet", "description", "quantity", "unit_price", "total", "is_void"]
    readonly_fields = fields


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    fields = ["business_date", "method", "currency", "amount", "amount_etb", "reference"]
    readonly_fields = fields


@admin.register(Folio)
class FolioAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "reservation", "status", "invoice_number", "opened_at"]
    list_filter = ["status"]
    search_fields = ["number", "name", "invoice_number"]
    inlines = [ChargeInline, PaymentInline]


@admin.register(CashierShift)
class CashierShiftAdmin(admin.ModelAdmin):
    list_display = ["id", "cashier", "status", "opened_at", "closed_at", "opening_float", "counted_cash_etb"]
