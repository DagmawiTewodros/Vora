from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("guests", views.GuestViewSet)

urlpatterns = router.urls
