from django.contrib import admin

from .models import BreakfastLog, MenuCategory, MenuItem, Order, OrderItem, Outlet


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "outlet", "table", "waiter", "status", "settlement", "created_at"]
    list_filter = ["outlet", "status", "settlement"]
    inlines = [OrderItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["name", "name_am", "category", "price", "is_active"]
    list_filter = ["category", "outlets", "is_active"]
    filter_horizontal = ["outlets"]


admin.site.register(Outlet)
admin.site.register(MenuCategory)
admin.site.register(BreakfastLog)
