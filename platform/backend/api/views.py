from rest_framework import viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from .models import Repository, App, Deployment
from .serializers import RepositorySerializer, AppSerializer

class RepositoryViewSet(viewsets.ModelViewSet):
  queryset = Repository.objects.all().order_by("-id")
  serializer_class = RepositorySerializer
  permission_classes = [permissions.AllowAny]

class AppViewSet(viewsets.ModelViewSet):
  queryset = App.objects.all().order_by("-id")
  serializer_class = AppSerializer
  permission_classes = [permissions.AllowAny]

  @action(detail=True, methods=["post"])
  def deploy(self, request, pk=None):
    app = self.get_object()
    d = Deployment.objects.create(app=app, status="queued")
    app.status="deploying"
    app.save(update_fields=["status"])
    return Response({"deployment_id": d.id, "status": d.status})

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health(request):
  return Response({"ok": True, "ts": timezone.now().isoformat()})
