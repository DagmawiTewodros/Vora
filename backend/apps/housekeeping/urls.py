from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("housekeeping/tasks", views.HousekeepingTaskViewSet)
router.register("housekeeping/rooms", views.RoomStatusViewSet, basename="room-status")

urlpatterns = router.urls
