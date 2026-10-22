from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("channels", views.ChannelViewSet)
router.register("channel-logs", views.SyncLogViewSet)

urlpatterns = [
    path("channels/webhook/<slug:code>/", views.ota_webhook),
    path("public/availability/", views.public_availability),
    path("public/book/", views.public_book),
] + router.urls
