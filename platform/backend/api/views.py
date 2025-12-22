import subprocess
import yaml
import os
import shutil
from pathlib import Path
from urllib.parse import quote

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

REPOS_DIR = Path("/runtime/repos")
REPOS_DIR.mkdir(parents=True, exist_ok=True)


def _audit(user, action, resource_type, resource_id, details=None):
  AuditLog.objects.create(
    user=user if user and user.is_authenticated else None,
    action=action,
    resource_type=resource_type,
    resource_id=resource_id,
    details=details or {},
  )

def _git_url(repo):
  url = repo.git_url
  token = (getattr(repo, "github_token", "") or "").strip()
  if token and url.startswith("https://") and "github.com" in url:
    return url.replace("https://", f"https://x-access-token:{quote(token, safe='')}@")
  return url

def _run(cmd, cwd=None):
  try:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
  except FileNotFoundError as e:
    result = subprocess.CompletedProcess(cmd, 1, "", f"Command not found: {cmd[0] if cmd else 'unknown'}. Error: {str(e)}")
    return result

class RepositoryViewSet(viewsets.ModelViewSet):
  queryset = Repository.objects.all().order_by("-id")
  serializer_class = RepositorySerializer

  def list(self, request, *args, **kwargs):
    import json
    import urllib.request
    import urllib.error
    
    # #region agent log
    try:
      auth_header = request.META.get("HTTP_AUTHORIZATION", "")
      log_data = {
        "sessionId": "debug-session",
        "runId": "api-request",
        "hypothesisId": "F",
        "location": "views.py:RepositoryViewSet.list",
        "message": "Repository list request",
        "data": {
          "user_authenticated": request.user.is_authenticated,
          "user": str(request.user) if request.user.is_authenticated else "anonymous",
          "has_auth_header": bool(auth_header),
          "auth_header_prefix": auth_header[:20] if auth_header else "",
          "origin": request.META.get("HTTP_ORIGIN", ""),
        },
        "timestamp": int(timezone.now().timestamp() * 1000)
      }
      req = urllib.request.Request('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', 
                                 data=json.dumps(log_data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
      urllib.request.urlopen(req, timeout=0.1).close()
    except: pass
    # #endregion
    
    return super().list(request, *args, **kwargs)

  def perform_create(self, serializer):
    obj = serializer.save()
    _audit(self.request.user, "create", "repository", obj.id, {"name": obj.name})

  def perform_update(self, serializer):
    obj = serializer.save()
    _audit(self.request.user, "update", "repository", obj.id, {"name": obj.name})

  def perform_destroy(self, instance):
    _audit(self.request.user, "delete", "repository", instance.id, {"name": instance.name})
    instance.delete()

  @action(detail=True, methods=["post"])
  def inspect(self, request, pk=None):
    """Inspect repository: clone it and analyze docker-compose.yml"""
    repo = self.get_object()
    repo.inspection_status = "inspecting"
    repo.save(update_fields=["inspection_status"])
    
    safe_name = repo.name.replace(" ", "_").lower()
    workdir = REPOS_DIR / f"inspect_{safe_name}"
    
    try:
      # Clean up any existing inspection directory
      if workdir.exists():
        shutil.rmtree(workdir)
      
      # Clone repository
      git_url = _git_url(repo)
      clone_result = _run(["git", "clone", "--depth", "1", "-b", repo.default_branch, git_url, str(workdir)])
      
      if clone_result.returncode != 0:
        error_msg = clone_result.stderr.strip() or clone_result.stdout.strip() or "Unknown git error"
        repo.inspection_status = "failed"
        repo.inspection_details = {
          "error": f"Git clone failed: {error_msg}",
          "git_stdout": clone_result.stdout,
          "git_stderr": clone_result.stderr,
        }
        repo.save(update_fields=["inspection_status", "inspection_details"])
        return Response({"error": f"Failed to clone repository: {error_msg}"}, status=status.HTTP_400_BAD_REQUEST)
      
      # Look for docker-compose.yml or docker-compose.yaml
      compose_files = []
      for filename in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
        compose_path = workdir / filename
        if compose_path.exists():
          compose_files.append(filename)
      
      inspection_details = {
        "compose_files_found": compose_files,
        "services": {},
        "issues": [],
        "recommendations": [],
      }
      
      if not compose_files:
        inspection_details["issues"].append("No docker-compose.yml file found. Keystone will use Dockerfile for deployment.")
        repo.inspection_status = "ready"
        repo.inspection_details = inspection_details
        repo.last_inspected_at = timezone.now()
        repo.save(update_fields=["inspection_status", "inspection_details", "last_inspected_at"])
        _audit(request.user, "inspect", "repository", repo.id, {"status": "ready", "compose_files": []})
        return Response({
          "status": "ready",
          "details": inspection_details,
          "message": "Repository inspected. No docker-compose.yml found - will use Dockerfile."
        })
      
      # Parse docker-compose.yml
      compose_path = workdir / compose_files[0]
      try:
        with open(compose_path, "r", encoding="utf-8") as f:
          compose_content = yaml.safe_load(f) or {}
      except Exception as e:
        inspection_details["issues"].append(f"Failed to parse docker-compose.yml: {str(e)}")
        repo.inspection_status = "failed"
        repo.inspection_details = inspection_details
        repo.save(update_fields=["inspection_status", "inspection_details"])
        return Response({"error": f"Failed to parse docker-compose.yml: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
      
      services = compose_content.get("services", {})
      inspection_details["services"] = {name: {
        "image": svc.get("image", ""),
        "build": svc.get("build", {}),
        "ports": svc.get("ports", []),
        "environment": svc.get("environment", {}),
        "labels": svc.get("labels", []),
        "networks": svc.get("networks", []),
      } for name, svc in services.items()}
      
      # Check for required Keystone deployment conditions
      main_service = None
      for name, svc in services.items():
        # Find the main application service (not db, redis, etc.)
        if not any(exclude in name.lower() for exclude in ["db", "database", "redis", "cache", "postgres", "mysql"]):
          if svc.get("build") or svc.get("image"):
            main_service = name
            break
      
      if not main_service and services:
        main_service = list(services.keys())[0]
      
      if main_service:
        main_svc = services[main_service]
        
        # Check for Traefik labels
        labels = main_svc.get("labels", [])
        if isinstance(labels, list):
          label_dict = {}
          for label in labels:
            if isinstance(label, str) and "=" in label:
              k, v = label.split("=", 1)
              label_dict[k] = v
          labels = label_dict
        elif isinstance(labels, dict):
          label_dict = labels
        else:
          label_dict = {}
        
        has_traefik = any("traefik" in k.lower() for k in label_dict.keys())
        
        if not has_traefik:
          inspection_details["recommendations"].append(
            "Add Traefik labels for reverse proxy routing. Keystone will add these during preparation."
          )
        
        # Check for network configuration
        networks = main_svc.get("networks", [])
        if not networks:
          inspection_details["recommendations"].append(
            "Add network configuration. Keystone will add 'platform' network during preparation."
          )
        
        # Check for port configuration
        ports = main_svc.get("ports", [])
        if not ports:
          inspection_details["recommendations"].append(
            "Service should expose a port. Keystone will handle port mapping during deployment."
          )
        
        inspection_details["main_service"] = main_service
        inspection_details["has_traefik"] = has_traefik
      
      # Store original compose content for reference
      inspection_details["original_compose"] = compose_content
      
      repo.inspection_status = "ready"
      repo.inspection_details = inspection_details
      repo.last_inspected_at = timezone.now()
      repo.save(update_fields=["inspection_status", "inspection_details", "last_inspected_at"])
      
      _audit(request.user, "inspect", "repository", repo.id, {"status": "ready", "compose_files": compose_files})
      
      return Response({
        "status": "ready",
        "details": inspection_details,
        "message": "Repository inspected successfully."
      })
      
    except Exception as e:
      import traceback
      repo.inspection_status = "failed"
      repo.inspection_details = {
        "error": str(e),
        "traceback": traceback.format_exc(),
      }
      repo.save(update_fields=["inspection_status", "inspection_details"])
      return Response({"error": f"Inspection failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  @action(detail=True, methods=["post"])
  def prepare(self, request, pk=None):
    """Prepare repository: standardize docker-compose.yml and add Traefik configs"""
    repo = self.get_object()
    
    if repo.inspection_status != "ready":
      return Response(
        {"error": "Repository must be inspected first. Run inspection before preparation."},
        status=status.HTTP_400_BAD_REQUEST
      )
    
    safe_name = repo.name.replace(" ", "_").lower()
    workdir = REPOS_DIR / f"inspect_{safe_name}"
    
    if not workdir.exists():
      return Response(
        {"error": "Inspection directory not found. Please run inspection first."},
        status=status.HTTP_400_BAD_REQUEST
      )
    
    try:
      # Find docker-compose file
      compose_path = None
      for filename in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
        path = workdir / filename
        if path.exists():
          compose_path = path
          break
      
      if not compose_path:
        # No docker-compose.yml - create a minimal one for Keystone
        compose_path = workdir / "docker-compose.yml"
        compose_content = {
          "version": "3.8",
          "services": {
            "app": {
              "build": {"context": "."},
              "networks": ["platform"],
              "labels": [],
            }
          },
          "networks": {
            "platform": {"external": True}
          }
        }
      else:
        # Load existing compose file
        with open(compose_path, "r", encoding="utf-8") as f:
          compose_content = yaml.safe_load(f) or {}
      
      services = compose_content.get("services", {})
      if not services:
        return Response({"error": "No services found in docker-compose.yml"}, status=status.HTTP_400_BAD_REQUEST)
      
      # Find or create main service
      main_service = None
      for name, svc in services.items():
        if not any(exclude in name.lower() for exclude in ["db", "database", "redis", "cache", "postgres", "mysql"]):
          if svc.get("build") or svc.get("image"):
            main_service = name
            break
      
      if not main_service:
        main_service = list(services.keys())[0]
      
      main_svc = services[main_service]
      
      # Ensure network configuration
      if "networks" not in main_svc:
        main_svc["networks"] = []
      if "platform" not in main_svc["networks"]:
        if isinstance(main_svc["networks"], list):
          main_svc["networks"].append("platform")
        else:
          main_svc["networks"]["platform"] = {}
      
      # Ensure networks section exists
      if "networks" not in compose_content:
        compose_content["networks"] = {}
      if "platform" not in compose_content["networks"]:
        compose_content["networks"]["platform"] = {"external": True}
      
      # Add Traefik labels
      if "labels" not in main_svc:
        main_svc["labels"] = []
      
      # Convert labels to dict if needed
      label_dict = {}
      if isinstance(main_svc["labels"], list):
        for label in main_svc["labels"]:
          if isinstance(label, str) and "=" in label:
            k, v = label.split("=", 1)
            label_dict[k] = v
          elif isinstance(label, dict):
            label_dict.update(label)
      elif isinstance(main_svc["labels"], dict):
        label_dict = main_svc["labels"].copy()
      
      # Add standard Traefik labels
      app_name_safe = repo.name.replace(" ", "-").lower()
      label_dict["traefik.enable"] = "true"
      label_dict[f"traefik.http.routers.{app_name_safe}.rule"] = f"Host(`{app_name_safe}.keystone.local`) || PathPrefix(`/{app_name_safe}`)"
      label_dict[f"traefik.http.routers.{app_name_safe}.entrypoints"] = "web"
      label_dict[f"traefik.http.services.{app_name_safe}.loadbalancer.server.port"] = "8000"
      
      # Convert back to list format (docker-compose prefers list)
      main_svc["labels"] = [f"{k}={v}" for k, v in label_dict.items()]
      
      # Remove port mappings (Keystone handles port allocation)
      if "ports" in main_svc:
        # Keep internal port info but remove host mapping
        ports = main_svc["ports"]
        if isinstance(ports, list):
          # Keep only internal ports for reference
          main_svc["_original_ports"] = ports
        main_svc.pop("ports", None)
      
      # Write updated compose file
      with open(compose_path, "w", encoding="utf-8") as f:
        yaml.dump(compose_content, f, default_flow_style=False, sort_keys=False)
      
      # Commit changes if git is configured
      commit_result = _run(["git", "add", str(compose_path.relative_to(workdir))], cwd=str(workdir))
      if commit_result.returncode == 0:
        commit_result = _run(["git", "commit", "-m", "Keystone: Standardize deployment configuration"], cwd=str(workdir))
        # Try to push if remote is configured (optional, may fail)
        _run(["git", "push"], cwd=str(workdir))
      
      # Store deployment config
      deployment_config = {
        "compose_file": str(compose_path.relative_to(workdir)),
        "main_service": main_service,
        "traefik_labels": label_dict,
        "networks": ["platform"],
        "prepared_at": timezone.now().isoformat(),
      }
      
      repo.deployment_config = deployment_config
      repo.prepared_for_deployment = True
      repo.save(update_fields=["deployment_config", "prepared_for_deployment"])
      
      _audit(request.user, "prepare", "repository", repo.id, {"config": deployment_config})
      
      return Response({
        "status": "prepared",
        "config": deployment_config,
        "message": "Repository prepared for deployment. Configuration standardized and Traefik labels added."
      })
      
    except Exception as e:
      import traceback
      return Response(
        {"error": f"Preparation failed: {str(e)}", "traceback": traceback.format_exc()},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
      )

class AppViewSet(viewsets.ModelViewSet):
  queryset = App.objects.all().order_by("-id")
  serializer_class = AppSerializer

  def list(self, request, *args, **kwargs):
    import json
    import urllib.request
    import urllib.error
    
    # #region agent log
    try:
      auth_header = request.META.get("HTTP_AUTHORIZATION", "")
      log_data = {
        "sessionId": "debug-session",
        "runId": "api-request",
        "hypothesisId": "F",
        "location": "views.py:AppViewSet.list",
        "message": "App list request",
        "data": {
          "user_authenticated": request.user.is_authenticated,
          "user": str(request.user) if request.user.is_authenticated else "anonymous",
          "has_auth_header": bool(auth_header),
          "auth_header_prefix": auth_header[:20] if auth_header else "",
          "origin": request.META.get("HTTP_ORIGIN", ""),
        },
        "timestamp": int(timezone.now().timestamp() * 1000)
      }
      req = urllib.request.Request('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', 
                                 data=json.dumps(log_data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
      urllib.request.urlopen(req, timeout=0.1).close()
    except: pass
    # #endregion
    
    return super().list(request, *args, **kwargs)

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
    if not app.repo.prepared_for_deployment:
      return Response(
        {"error": "Repository must be inspected and prepared before deployment. Please run inspection and preparation first."},
        status=status.HTTP_400_BAD_REQUEST
      )
    d = Deployment.objects.create(app=app, status="queued", deployment_type="initial")
    app.status="deploying"
    app.save(update_fields=["status"])
    _audit(request.user, "deploy", "app", app.id, {"deployment_id": d.id, "type": "initial"})
    return Response({"deployment_id": d.id, "status": d.status})

  @action(detail=True, methods=["post"], url_path="update")
  def update_deploy(self, request, pk=None):
    app = self.get_object()
    if not app.repo.prepared_for_deployment:
      return Response(
        {"error": "Repository must be inspected and prepared before deployment. Please run inspection and preparation first."},
        status=status.HTTP_400_BAD_REQUEST
      )
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
    import json
    import urllib.request
    import urllib.error
    
    # #region agent log
    try:
      log_data = {
        "sessionId": "debug-session",
        "runId": "container-status",
        "hypothesisId": "E",
        "location": "views.py:container_status:439",
        "message": "container_status called",
        "data": {"app_id": pk, "user_authenticated": request.user.is_authenticated, "user": str(request.user) if request.user.is_authenticated else "anonymous"},
        "timestamp": int(timezone.now().timestamp() * 1000)
      }
      req = urllib.request.Request('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', 
                                 data=json.dumps(log_data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
      urllib.request.urlopen(req, timeout=0.1).close()
    except: pass
    # #endregion
    
    app = self.get_object()
    safe = app.name.replace(" ","_").lower()
    cname = f"app_{safe}"
    
    # Try to find docker command
    docker_cmd = None
    for cmd in ["docker", "docker.io"]:
      result = subprocess.run(["which", cmd], capture_output=True, text=True)
      if result.returncode == 0 and result.stdout.strip():
        docker_cmd = result.stdout.strip()
        break
    
    if not docker_cmd:
      # Check common paths
      for path in ["/usr/bin/docker", "/usr/bin/docker.io", "/usr/local/bin/docker"]:
        if os.path.exists(path):
          docker_cmd = path
          break
    
    if not docker_cmd:
      # #region agent log
      try:
        log_data = {
          "sessionId": "debug-session",
          "runId": "container-status",
          "hypothesisId": "E",
          "location": "views.py:container_status:470",
          "message": "Docker command not found in backend",
          "data": {"app_id": pk, "cname": cname},
          "timestamp": int(timezone.now().timestamp() * 1000)
        }
        req = urllib.request.Request('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', 
                                   data=json.dumps(log_data).encode('utf-8'),
                                   headers={'Content-Type': 'application/json'},
                                   method='POST')
        urllib.request.urlopen(req, timeout=0.1).close()
      except: pass
      # #endregion
      return Response({"status": "unknown", "details": "Docker command not available in backend container"})
    
    try:
      result = subprocess.run(
        [docker_cmd, "ps", "--filter", f"name={cname}", "--format", "{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=5,
      )
      # #region agent log
      try:
        log_data = {
          "sessionId": "debug-session",
          "runId": "container-status",
          "hypothesisId": "E",
          "location": "views.py:container_status:490",
          "message": "Docker ps result",
          "data": {"returncode": result.returncode, "stdout": result.stdout[:100], "stderr": result.stderr[:100]},
          "timestamp": int(timezone.now().timestamp() * 1000)
        }
        req = urllib.request.Request('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', 
                                   data=json.dumps(log_data).encode('utf-8'),
                                   headers={'Content-Type': 'application/json'},
                                   method='POST')
        urllib.request.urlopen(req, timeout=0.1).close()
      except: pass
      # #endregion
      if result.returncode == 0 and result.stdout.strip():
        return Response({"status": "running", "details": result.stdout.strip()})
      return Response({"status": "stopped"})
    except Exception as e:
      # #region agent log
      try:
        log_data = {
          "sessionId": "debug-session",
          "runId": "container-status",
          "hypothesisId": "E",
          "location": "views.py:container_status:505",
          "message": "Exception in container_status",
          "data": {"error": str(e)[:200]},
          "timestamp": int(timezone.now().timestamp() * 1000)
        }
        req = urllib.request.Request('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', 
                                   data=json.dumps(log_data).encode('utf-8'),
                                   headers={'Content-Type': 'application/json'},
                                   method='POST')
        urllib.request.urlopen(req, timeout=0.1).close()
      except: pass
      # #endregion
      return Response({"status": "error", "details": str(e)[:200]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
