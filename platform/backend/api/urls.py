from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RepositoryViewSet, AppViewSet, health

router = DefaultRouter()
router.register(r"repos", RepositoryViewSet, basename="repos")
router.register(r"apps", AppViewSet, basename="apps")

urlpatterns = [
  path("health", health),
  path("", include(router.urls)),
]
