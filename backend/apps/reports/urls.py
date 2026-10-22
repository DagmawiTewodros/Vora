from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("reports/night-audits", views.NightAuditViewSet)

urlpatterns = [
    path("reports/daily/", views.daily),
    path("reports/summary/", views.summary),
    path("reports/guest-register/", views.guest_register),
    path("reports/breakfast/", views.breakfast),
    path("reports/night-audit/run/", views.run_night_audit),
] + router.urls
