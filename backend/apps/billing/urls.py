from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("folios", views.FolioViewSet)
router.register("charges", views.ChargeViewSet)
router.register("payments", views.PaymentViewSet)
router.register("shifts", views.CashierShiftViewSet)

urlpatterns = router.urls
