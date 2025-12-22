import subprocess
from pathlib import Path

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, Deployment, Repository, App
from .serializers import (
  AppSerializer,
  AuditLogSerializer,
  DeploymentSerializer,
  RepositorySerializer,
)


def _audit(user, action, resource_type, resource_id, details=None):
  AuditLog.objects.create(
    user=user if user and user.is_authenticated else None,
    action=action,
    resource_type=resource_type,
    resource_id=resource_id,
    details=details or {},
  )

class RepositoryViewSet(viewsets.ModelViewSet):
  queryset = Repository.objects.all().order_by("-id")
  serializer_class = RepositorySerializer

  def perform_create(self, serializer):
    obj = serializer.save()
    _audit(self.request.user, "create", "repository", obj.id, {"name": obj.name})

  def perform_update(self, serializer):
    obj = serializer.save()
    _audit(self.request.user, "update", "repository", obj.id, {"name": obj.name})

  def perform_destroy(self, instance):
    _audit(self.request.user, "delete", "repository", instance.id, {"name": instance.name})
    instance.delete()

class AppViewSet(viewsets.ModelViewSet):
  queryset = App.objects.all().order_by("-id")
  serializer_class = AppSerializer

  def perform_create(self, serializer):
    obj = serializer.save()
    _audit(self.request.user, "create", "app", obj.id, {"name": obj.name, "repo_id": obj.repo_id})

  def perform_update(self, serializer):
    obj = serializer.save()
    _audit(self.request.user, "update", "app", obj.id, {"name": obj.name, "repo_id": obj.repo_id})

  def perform_destroy(self, instance):
    _audit(self.request.user, "delete", "app", instance.id, {"name": instance.name, "repo_id": instance.repo_id})
    instance.delete()

  @action(detail=True, methods=["post"])
  def deploy(self, request, pk=None):
    app = self.get_object()
    d = Deployment.objects.create(app=app, status="queued", deployment_type="initial")
    app.status="deploying"
    app.save(update_fields=["status"])
    _audit(request.user, "deploy", "app", app.id, {"deployment_id": d.id, "type": "initial"})
    return Response({"deployment_id": d.id, "status": d.status})

  @action(detail=True, methods=["post"], url_path="update")
  def update_deploy(self, request, pk=None):
    app = self.get_object()
    d = Deployment.objects.create(app=app, status="queued", deployment_type="update")
    app.status="deploying"
    app.save(update_fields=["status"])
    _audit(request.user, "deploy", "app", app.id, {"deployment_id": d.id, "type": "update"})
    return Response({"deployment_id": d.id, "status": d.status})

  @action(detail=True, methods=["post"])
  def rollback(self, request, pk=None):
    app = self.get_object()
    successes = list(app.deployments.filter(status="success").order_by("-ended_at").values_list("image_tag", flat=True))
    if len(successes) < 2:
      return Response({"error": "No previous successful deployment to roll back to."}, status=status.HTTP_400_BAD_REQUEST)

    target_image = successes[1]
    d = Deployment.objects.create(app=app, status="queued", deployment_type="rollback", image_tag=target_image)
    app.status="deploying"
    app.save(update_fields=["status"])
    _audit(request.user, "rollback", "app", app.id, {"deployment_id": d.id, "image_tag": target_image})
    return Response({"deployment_id": d.id, "status": d.status, "image_tag": target_image})

  @action(detail=True, methods=["get"])
  def container_status(self, request, pk=None):
    app = self.get_object()
    safe = app.name.replace(" ","_").lower()
    cname = f"app_{safe}"
    result = subprocess.run(
      ["docker", "ps", "--filter", f"name={cname}", "--format", "{{.Status}}"],
      capture_output=True,
      text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
      return Response({"status": "running", "details": result.stdout.strip()})
    return Response({"status": "stopped"})


class DeploymentViewSet(viewsets.ReadOnlyModelViewSet):
  serializer_class = DeploymentSerializer
  queryset = Deployment.objects.select_related("app", "app__repo").all().order_by("-created_at")

  def get_queryset(self):
    qs = super().get_queryset()
    app_id = self.request.query_params.get("app")
    if app_id:
      qs = qs.filter(app_id=app_id)
    return qs

  @action(detail=True, methods=["get"])
  def logs(self, request, pk=None):
    dep = self.get_object()
    if not dep.logs_path:
      return Response({"error": "No logs available"}, status=status.HTTP_404_NOT_FOUND)
    p = Path(dep.logs_path)
    if not p.exists():
      return Response({"error": "Log file not found"}, status=status.HTTP_404_NOT_FOUND)
    try:
      return Response({"deployment_id": dep.id, "logs": p.read_text(encoding="utf-8", errors="replace")})
    except Exception as e:  # noqa: BLE001
      return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
  serializer_class = AuditLogSerializer
  queryset = AuditLog.objects.select_related("user").all()


class AuthTokenView(APIView):
  permission_classes = [permissions.AllowAny]

  def post(self, request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    from django.contrib.auth import authenticate  # local import
    user = authenticate(request, username=username, password=password)
    if not user:
      return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "username": user.username})


class LogoutView(APIView):
  def post(self, request):
    Token.objects.filter(user=request.user).delete()
    return Response({"ok": True})

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health(request):
  return Response({"ok": True, "ts": timezone.now().isoformat()})
