from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AppViewSet,
    DeploymentViewSet,
    LoginView,
    LogoutView,
    health,
)

router = DefaultRouter()
router.register(r"apps", AppViewSet, basename="apps")
router.register(r"deployments", DeploymentViewSet, basename="deployments")

urlpatterns = [
    path("health/", health),
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("", include(router.urls)),
]
