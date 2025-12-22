from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
  AppViewSet,
  AuditLogViewSet,
  AuthTokenView,
  DeploymentViewSet,
  LogoutView,
  RepositoryViewSet,
  health,
)

router = DefaultRouter()
router.register(r"repos", RepositoryViewSet, basename="repos")
router.register(r"apps", AppViewSet, basename="apps")
router.register(r"deployments", DeploymentViewSet, basename="deployments")
router.register(r"audit", AuditLogViewSet, basename="audit")

urlpatterns = [
  path("health", health),
  path("auth/token", AuthTokenView.as_view()),
  path("auth/logout", LogoutView.as_view()),
  path("", include(router.urls)),
]
