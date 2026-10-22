from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("pos/outlets", views.OutletViewSet)
router.register("pos/categories", views.MenuCategoryViewSet)
router.register("pos/menu", views.MenuItemViewSet)
router.register("pos/orders", views.OrderViewSet)
router.register("pos/breakfast", views.BreakfastLogViewSet)

urlpatterns = [
    path("pos/kitchen/", views.kitchen_tickets),
    path("pos/kitchen/items/<int:item_id>/", views.kitchen_item_status),
] + router.urls
