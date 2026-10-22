from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("staff", views.StaffViewSet)
router.register("settings", views.HotelSettingsViewSet, basename="settings")
router.register("exchange-rates", views.ExchangeRateViewSet)
router.register("audit-log", views.AuditLogViewSet)

urlpatterns = [
    path("auth/login/", views.password_login),
    path("auth/pin/", views.pin_login),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/me/", views.me),
    path("calendar/today/", views.calendar_today),
] + router.urls
