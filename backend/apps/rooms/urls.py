from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("room-types", views.RoomTypeViewSet)
router.register("rooms", views.RoomViewSet)
router.register("rate-plans", views.RatePlanViewSet)

urlpatterns = router.urls
