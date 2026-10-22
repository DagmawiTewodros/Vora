from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("inventory/suppliers", views.SupplierViewSet)
router.register("inventory/items", views.InventoryItemViewSet)
router.register("inventory/recipes", views.RecipeLineViewSet)
router.register("inventory/movements", views.StockMovementViewSet)
router.register("inventory/purchase-orders", views.PurchaseOrderViewSet)

urlpatterns = router.urls
