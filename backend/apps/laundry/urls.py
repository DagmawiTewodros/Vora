from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("laundry/prices", views.LaundryPriceViewSet)
router.register("laundry/tickets", views.LaundryTicketViewSet)

urlpatterns = router.urls
