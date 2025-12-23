"""
Keystone API Views

Simple 3-step workflow:
1. Import Repo - POST /api/apps/ with {name, git_url, branch}
2. Prepare - POST /api/apps/{id}/prepare/ - Configure for Traefik
3. Deploy - POST /api/apps/{id}/deploy/ - Build and run container
"""
import os
import shutil
import subprocess
from pathlib import Path

import yaml
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import App, Deployment
from .serializers import AppSerializer, DeploymentSerializer

# Directories for repos and logs
REPOS_DIR = Path("/runtime/repos")
LOGS_DIR = Path("/runtime/logs")
REPOS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Traefik network name
TRAEFIK_NETWORK = "keystone_web"


def run_cmd(cmd, cwd=None, timeout=300):
    """Run a shell command and return result."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


class AppViewSet(viewsets.ModelViewSet):
    """
    CRUD for Apps + prepare/deploy actions.
    """
    queryset = App.objects.all().order_by("-created_at")
    serializer_class = AppSerializer
    
    @action(detail=True, methods=["post"])
    def prepare(self, request, pk=None):
        """
        Step 2: Prepare repo for Traefik deployment.
        - Clone the repo
        - Detect structure (Django backend, frontend, etc.)
        - Generate Traefik labels
        """
        app = self.get_object()
        
        if app.status not in ["imported", "failed", "prepared"]:
            return Response(
                {"error": f"Cannot prepare app in status: {app.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        app.status = "preparing"
        app.error_message = ""
        app.save()
        
        try:
            # Clone or update repo
            repo_dir = REPOS_DIR / app.slug
            
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            
            # Clone repo
            code, out, err = run_cmd(
                ["git", "clone", "--depth", "1", "-b", app.branch, app.git_url, str(repo_dir)]
            )
            
            if code != 0:
                raise Exception(f"Git clone failed: {err or out}")
            
            # Detect app structure
            has_dockerfile = (repo_dir / "Dockerfile").exists()
            has_compose = (repo_dir / "docker-compose.yml").exists() or (repo_dir / "compose.yml").exists()
            has_requirements = (repo_dir / "requirements.txt").exists()
            has_manage_py = (repo_dir / "manage.py").exists()
            has_package_json = (repo_dir / "package.json").exists()
            
            structure = {
                "dockerfile": has_dockerfile,
                "docker_compose": has_compose,
                "django": has_manage_py,
                "python": has_requirements,
                "node": has_package_json,
            }
            
            # Generate Dockerfile if needed
            if not has_dockerfile:
                if has_manage_py:
                    # Django app
                    dockerfile_content = self._generate_django_dockerfile()
                elif has_package_json:
                    # Node app
                    dockerfile_content = self._generate_node_dockerfile()
                else:
                    raise Exception("No Dockerfile found and couldn't detect app type")
                
                with open(repo_dir / "Dockerfile", "w") as f:
                    f.write(dockerfile_content)
            
            # Set Traefik rule (path-based routing)
            app.traefik_rule = f"PathPrefix(`/{app.slug}`)"
            app.status = "prepared"
            app.save()
            
            return Response({
                "status": "prepared",
                "structure": structure,
                "traefik_rule": app.traefik_rule,
                "message": f"App prepared. Will be accessible at /{app.slug}"
            })
            
        except Exception as e:
            app.status = "failed"
            app.error_message = str(e)
            app.save()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=["post"])
    def deploy(self, request, pk=None):
        """
        Step 3: Deploy the app.
        - Build Docker image
        - Run container with Traefik labels
        """
        app = self.get_object()
        
        if app.status not in ["prepared", "running", "stopped", "failed"]:
            return Response(
                {"error": f"App must be prepared first. Current status: {app.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create deployment record
        deployment = Deployment.objects.create(app=app, status="running")
        
        app.status = "deploying"
        app.error_message = ""
        app.save()
        
        logs = []
        
        try:
            repo_dir = REPOS_DIR / app.slug
            
            if not repo_dir.exists():
                raise Exception("Repo not found. Please prepare first.")
            
            # Stop existing container if any
            container_name = f"keystone-app-{app.slug}"
            run_cmd(["docker", "stop", container_name])
            run_cmd(["docker", "rm", container_name])
            
            # Build image
            image_tag = f"keystone/{app.slug}:latest"
            logs.append(f"Building image: {image_tag}")
            
            code, out, err = run_cmd(
                ["docker", "build", "-t", image_tag, "."],
                cwd=str(repo_dir),
                timeout=600
            )
            logs.append(f"Build output:\n{out}\n{err}")
            
            if code != 0:
                raise Exception(f"Docker build failed: {err or out}")
            
            # Prepare environment variables
            env_args = []
            for key, value in (app.env_vars or {}).items():
                env_args.extend(["-e", f"{key}={value}"])
            
            # Run container with Traefik labels
            docker_run_cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--network", TRAEFIK_NETWORK,
                "--restart", "unless-stopped",
                # Traefik labels
                "-l", "traefik.enable=true",
                "-l", f"traefik.http.routers.{app.slug}.rule={app.traefik_rule}",
                "-l", f"traefik.http.routers.{app.slug}.entrypoints=web",
                "-l", f"traefik.http.services.{app.slug}.loadbalancer.server.port={app.container_port}",
                # Strip path prefix so app receives clean URLs
                "-l", f"traefik.http.middlewares.{app.slug}-strip.stripprefix.prefixes=/{app.slug}",
                "-l", f"traefik.http.routers.{app.slug}.middlewares={app.slug}-strip",
            ] + env_args + [image_tag]
            
            logs.append(f"Running container: {container_name}")
            code, out, err = run_cmd(docker_run_cmd)
            logs.append(f"Run output:\n{out}\n{err}")
            
            if code != 0:
                raise Exception(f"Docker run failed: {err or out}")
            
            # Get container ID
            app.container_id = out.strip()[:12]
            app.status = "running"
            app.save()
            
            deployment.status = "success"
            deployment.logs = "\n".join(logs)
            deployment.finished_at = timezone.now()
            deployment.save()
            
            return Response({
                "status": "running",
                "container_id": app.container_id,
                "url": f"/{app.slug}",
                "message": f"App deployed! Access at http://YOUR_VPS_IP/{app.slug}"
            })
            
        except Exception as e:
            app.status = "failed"
            app.error_message = str(e)
            app.save()
            
            deployment.status = "failed"
            deployment.error = str(e)
            deployment.logs = "\n".join(logs)
            deployment.finished_at = timezone.now()
            deployment.save()
            
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        """Stop a running app."""
        app = self.get_object()
        container_name = f"keystone-app-{app.slug}"
        
        run_cmd(["docker", "stop", container_name])
        app.status = "stopped"
        app.save()
        
        return Response({"status": "stopped"})
    
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """Get container logs."""
        app = self.get_object()
        container_name = f"keystone-app-{app.slug}"
        
        code, out, err = run_cmd(["docker", "logs", "--tail", "100", container_name])
        
        return Response({"logs": out or err})
    
    def _generate_django_dockerfile(self):
        """Generate Dockerfile for Django app."""
        return '''FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy app
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "config.wsgi:application"]
'''
    
    def _generate_node_dockerfile(self):
        """Generate Dockerfile for Node app."""
        return '''FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build 2>/dev/null || true

EXPOSE 3000

CMD ["npm", "start"]
'''


class DeploymentViewSet(viewsets.ReadOnlyModelViewSet):
    """View deployment history."""
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer
    
    def get_queryset(self):
        qs = super().get_queryset()
        app_id = self.request.query_params.get("app")
        if app_id:
            qs = qs.filter(app_id=app_id)
        return qs


# =============================================================================
# Auth Views
# =============================================================================

class LoginView(APIView):
    """Get auth token."""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        from django.contrib.auth import authenticate
        
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"error": "Invalid credentials"}, status=400)
        
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class LogoutView(APIView):
    """Invalidate auth token."""
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"ok": True})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health(request):
    """Health check endpoint."""
    return Response({"status": "ok", "service": "keystone"})
