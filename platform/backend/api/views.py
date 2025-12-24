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
import copy
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


def inject_traefik_config(compose_path, app_slug, app_traefik_rule):
    """
    Modify a docker-compose.yml to add Traefik routing configuration.
    - Adds Traefik labels to web-facing services
    - Connects services to keystone_web network
    - Removes conflicting port mappings (80, 443)
    - Converts relative volume mounts to absolute paths
    - Backs up original file
    """
    # Read original compose file
    with open(compose_path, 'r') as f:
        compose_data = yaml.safe_load(f)
    
    # Get the absolute path of the repo directory for volume mount conversion
    repo_dir = compose_path.parent
    
    # Convert container path to host path for Docker-in-Docker volume mounts
    # Container has /runtime/repos, but Docker needs host path
    host_runtime_path = os.environ.get('HOST_RUNTIME_PATH', '/runtime')
    container_runtime_path = '/runtime'
    
    if not compose_data or 'services' not in compose_data:
        raise Exception("Invalid docker-compose.yml: no services found")
    
    # Backup original
    backup_path = compose_path.parent / f"{compose_path.name}.original"
    shutil.copy(compose_path, backup_path)
    
    modified_services = []
    
    # Common web service names to look for
    web_service_names = ['nginx', 'frontend', 'web', 'proxy', 'gateway', 'app']
    backend_service_names = ['backend', 'api', 'server', 'django', 'flask', 'fastapi']
    
    # Process ALL services - convert volumes and add network
    for service_name, service_config in compose_data['services'].items():
        if service_config is None:
            service_config = {}
            compose_data['services'][service_name] = service_config
        
        # Convert relative volume mounts to absolute HOST paths
        # This is needed for Docker-in-Docker: the path must be valid on the Docker host
        if 'volumes' in service_config:
            new_volumes = []
            for vol in service_config['volumes']:
                if isinstance(vol, str):
                    # Short syntax: ./host:container or ./host:container:ro
                    if vol.startswith('./') or vol.startswith('../'):
                        parts = vol.split(':')
                        host_path = parts[0]
                        # Convert relative to absolute (container path)
                        container_abs_path = str((repo_dir / host_path).resolve())
                        # Convert container path to host path
                        if container_abs_path.startswith(container_runtime_path):
                            host_abs_path = container_abs_path.replace(container_runtime_path, host_runtime_path, 1)
                        else:
                            host_abs_path = container_abs_path
                        parts[0] = host_abs_path
                        vol = ':'.join(parts)
                    new_volumes.append(vol)
                elif isinstance(vol, dict):
                    # Long syntax with 'source' key
                    source = vol.get('source', '')
                    if source.startswith('./') or source.startswith('../'):
                        container_abs_path = str((repo_dir / source).resolve())
                        if container_abs_path.startswith(container_runtime_path):
                            host_abs_path = container_abs_path.replace(container_runtime_path, host_runtime_path, 1)
                        else:
                            host_abs_path = container_abs_path
                        vol['source'] = host_abs_path
                    new_volumes.append(vol)
                else:
                    new_volumes.append(vol)
            service_config['volumes'] = new_volumes
        
        is_web_service = False
        service_port = None
        
        # Check if service has ports that look like web ports
        ports = service_config.get('ports', [])
        for port in ports:
            port_str = str(port)
            # Look for common web ports (80, 443, 3000, 8000, 8080, 5000)
            if any(p in port_str for p in ['80:', '443:', '3000:', '8000:', '8080:', '5000:', ':80', ':443']):
                is_web_service = True
                # Extract the container port
                if ':' in port_str:
                    parts = port_str.split(':')
                    service_port = parts[-1].split('/')[0]  # Handle "8000:8000/tcp"
                break
        
        # Check if service name suggests it's a web service
        service_name_lower = service_name.lower()
        if any(name in service_name_lower for name in web_service_names):
            is_web_service = True
            if not service_port:
                service_port = "80"
        elif any(name in service_name_lower for name in backend_service_names):
            is_web_service = True
            if not service_port:
                service_port = "8000"
        
        if is_web_service:
            # Add Traefik labels
            labels = service_config.get('labels', [])
            if isinstance(labels, dict):
                labels = [f"{k}={v}" for k, v in labels.items()]
            
            # Create unique router name for this service
            router_name = f"{app_slug}-{service_name}"
            
            # Determine the path prefix for this service
            if service_name_lower in ['nginx', 'frontend', 'web', 'proxy', 'gateway']:
                # Frontend/proxy gets the main path
                path_prefix = f"/{app_slug}"
            else:
                # Backend services get a subpath
                path_prefix = f"/{app_slug}/api" if 'backend' in service_name_lower or 'api' in service_name_lower else f"/{app_slug}/{service_name}"
            
            traefik_labels = [
                "traefik.enable=true",
                f"traefik.http.routers.{router_name}.rule=PathPrefix(`{path_prefix}`)",
                f"traefik.http.routers.{router_name}.entrypoints=web",
                f"traefik.http.services.{router_name}.loadbalancer.server.port={service_port}",
                f"traefik.http.middlewares.{router_name}-strip.stripprefix.prefixes={path_prefix}",
                f"traefik.http.routers.{router_name}.middlewares={router_name}-strip",
            ]
            
            # Add labels
            for label in traefik_labels:
                if label not in labels:
                    labels.append(label)
            
            service_config['labels'] = labels
            
            # Remove conflicting port mappings (ports that would conflict on host)
            if 'ports' in service_config:
                new_ports = []
                for port in service_config['ports']:
                    port_str = str(port)
                    # Keep internal-only ports, remove host-mapped ones
                    if ':' not in port_str:
                        new_ports.append(port)
                    else:
                        # Check if it's mapping to host ports 80 or 443 (which Traefik uses)
                        host_port = port_str.split(':')[0]
                        if host_port not in ['80', '443']:
                            # Keep non-conflicting ports but comment them out by not adding
                            pass
                # Remove ports section if empty, Traefik handles routing
                if new_ports:
                    service_config['ports'] = new_ports
                else:
                    service_config.pop('ports', None)
            
            # Ensure service is on keystone_web network
            networks = service_config.get('networks', [])
            if isinstance(networks, list):
                if TRAEFIK_NETWORK not in networks:
                    networks.append(TRAEFIK_NETWORK)
            elif isinstance(networks, dict):
                if TRAEFIK_NETWORK not in networks:
                    networks[TRAEFIK_NETWORK] = {}
            else:
                networks = [TRAEFIK_NETWORK]
            service_config['networks'] = networks
            
            modified_services.append({
                "name": service_name,
                "port": service_port,
                "path": path_prefix
            })
    
    # Add keystone_web to top-level networks as external
    if 'networks' not in compose_data:
        compose_data['networks'] = {}
    
    compose_data['networks'][TRAEFIK_NETWORK] = {
        'external': True
    }
    
    # Write modified compose file
    with open(compose_path, 'w') as f:
        yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
    
    return modified_services


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
    
    def _find_dockerfile_or_app(self, repo_dir):
        """
        Find Dockerfile or app files in repo, checking root and common subdirectories.
        Returns: (dockerfile_path, app_type, build_context)
        """
        # Common subdirectory names to check
        subdirs_to_check = ["", "backend", "app", "src", "api", "server"]
        
        for subdir in subdirs_to_check:
            check_dir = repo_dir / subdir if subdir else repo_dir
            if not check_dir.exists():
                continue
                
            # Check for Dockerfile
            if (check_dir / "Dockerfile").exists():
                return (check_dir / "Dockerfile", "dockerfile", check_dir)
            
            # Check for Django app
            if (check_dir / "manage.py").exists():
                return (None, "django", check_dir)
            
            # Check for Node app
            if (check_dir / "package.json").exists():
                return (None, "node", check_dir)
            
            # Check for Python app with requirements.txt
            if (check_dir / "requirements.txt").exists():
                return (None, "python", check_dir)
        
        return (None, None, None)

    @action(detail=True, methods=["post"])
    def prepare(self, request, pk=None):
        """
        Step 2: Prepare repo for Traefik deployment.
        - Clone the repo
        - Detect structure (Django backend, frontend, docker-compose, etc.)
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
            
            # Check for docker-compose.yml first (multi-service apps)
            has_compose = (repo_dir / "docker-compose.yml").exists() or (repo_dir / "compose.yml").exists()
            compose_file = "docker-compose.yml" if (repo_dir / "docker-compose.yml").exists() else "compose.yml" if (repo_dir / "compose.yml").exists() else None
            
            # Detect app structure at root level
            has_dockerfile = (repo_dir / "Dockerfile").exists()
            has_requirements = (repo_dir / "requirements.txt").exists()
            has_manage_py = (repo_dir / "manage.py").exists()
            has_package_json = (repo_dir / "package.json").exists()
            
            # Find Dockerfile or app in subdirectories
            dockerfile_path, app_type, build_context = self._find_dockerfile_or_app(repo_dir)
            
            structure = {
                "dockerfile": has_dockerfile or (dockerfile_path is not None),
                "docker_compose": has_compose,
                "django": has_manage_py or app_type == "django",
                "python": has_requirements or app_type == "python",
                "node": has_package_json or app_type == "node",
                "build_context": str(build_context.relative_to(repo_dir)) if build_context and build_context != repo_dir else ".",
                "deploy_mode": "compose" if has_compose else "dockerfile",
            }
            
            # Determine deployment strategy
            if has_compose:
                # Multi-service app with docker-compose.yml
                # INJECT TRAEFIK CONFIGURATION into the compose file
                compose_path = repo_dir / compose_file
                modified_services = inject_traefik_config(
                    compose_path, 
                    app.slug, 
                    f"PathPrefix(`/{app.slug}`)"
                )
                
                # Store the compose file path for deploy step
                app.env_vars = app.env_vars or {}
                app.env_vars["_keystone_deploy_mode"] = "compose"
                app.env_vars["_keystone_compose_file"] = compose_file
                
                structure["message"] = "Modified docker-compose.yml with Traefik routing"
                structure["modified_services"] = modified_services
                structure["traefik_injected"] = True
                
            elif dockerfile_path:
                # Found Dockerfile (possibly in subdirectory)
                app.env_vars = app.env_vars or {}
                app.env_vars["_keystone_deploy_mode"] = "dockerfile"
                app.env_vars["_keystone_build_context"] = str(build_context.relative_to(repo_dir)) if build_context != repo_dir else "."
                
            elif has_dockerfile:
                # Dockerfile at root
                app.env_vars = app.env_vars or {}
                app.env_vars["_keystone_deploy_mode"] = "dockerfile"
                app.env_vars["_keystone_build_context"] = "."
                
            elif app_type == "django":
                # Generate Django Dockerfile
                dockerfile_content = self._generate_django_dockerfile()
                with open(build_context / "Dockerfile", "w") as f:
                    f.write(dockerfile_content)
                app.env_vars = app.env_vars or {}
                app.env_vars["_keystone_deploy_mode"] = "dockerfile"
                app.env_vars["_keystone_build_context"] = str(build_context.relative_to(repo_dir)) if build_context != repo_dir else "."
                structure["generated_dockerfile"] = True
                
            elif app_type == "node":
                # Generate Node Dockerfile
                dockerfile_content = self._generate_node_dockerfile()
                with open(build_context / "Dockerfile", "w") as f:
                    f.write(dockerfile_content)
                app.env_vars = app.env_vars or {}
                app.env_vars["_keystone_deploy_mode"] = "dockerfile"
                app.env_vars["_keystone_build_context"] = str(build_context.relative_to(repo_dir)) if build_context != repo_dir else "."
                structure["generated_dockerfile"] = True
                
            else:
                raise Exception(
                    "No Dockerfile or docker-compose.yml found, and couldn't detect app type. "
                    "Checked: root, backend/, app/, src/, api/, server/ directories. "
                    "Please add a Dockerfile or docker-compose.yml to your repository."
                )
            
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
        - For docker-compose apps: use docker compose up
        - For single Dockerfile apps: build and run with Traefik labels
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
            
            # Get deployment mode from env_vars (set during prepare)
            env_vars = app.env_vars or {}
            deploy_mode = env_vars.get("_keystone_deploy_mode", "dockerfile")
            
            if deploy_mode == "compose":
                # Deploy using docker-compose
                return self._deploy_compose(app, deployment, repo_dir, logs)
            else:
                # Deploy using single Dockerfile
                return self._deploy_dockerfile(app, deployment, repo_dir, logs)
            
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

    def _deploy_compose(self, app, deployment, repo_dir, logs):
        """Deploy app using docker-compose with Traefik routing."""
        env_vars = app.env_vars or {}
        compose_file = env_vars.get("_keystone_compose_file", "docker-compose.yml")
        
        logs.append(f"Deploying with docker-compose: {compose_file}")
        logs.append(f"Traefik routing: {app.traefik_rule}")
        
        # Create a project name based on app slug
        project_name = f"keystone-{app.slug}"
        
        # Stop existing compose stack if any
        logs.append("Stopping existing containers...")
        run_cmd(
            ["docker", "compose", "-p", project_name, "-f", compose_file, "down", "--remove-orphans"],
            cwd=str(repo_dir),
            timeout=120
        )
        
        # Handle .env file - copy from .env.example if exists and .env doesn't
        env_example = repo_dir / ".env.example"
        env_file = repo_dir / ".env"
        if env_example.exists() and not env_file.exists():
            shutil.copy(env_example, env_file)
            logs.append("Created .env from .env.example")
        
        # Prepare environment variables to inject
        env_file_content = []
        for key, value in env_vars.items():
            if not key.startswith("_keystone_"):  # Skip internal keys
                env_file_content.append(f"{key}={value}")
        
        # Append Keystone env vars to .env file
        if env_file_content:
            mode = "a" if env_file.exists() else "w"
            with open(env_file, mode) as f:
                f.write("\n# Keystone injected vars\n")
                f.write("\n".join(env_file_content) + "\n")
            logs.append(f"Added {len(env_file_content)} env vars to .env")
        
        # Build images
        logs.append("Building images...")
        code, out, err = run_cmd(
            ["docker", "compose", "-p", project_name, "-f", compose_file, "build", "--no-cache"],
            cwd=str(repo_dir),
            timeout=900
        )
        logs.append(f"Build output:\n{out}\n{err}")
        
        if code != 0:
            raise Exception(f"Docker compose build failed: {err or out}")
        
        # Start services
        logs.append("Starting services with Traefik routing...")
        code, out, err = run_cmd(
            ["docker", "compose", "-p", project_name, "-f", compose_file, "up", "-d"],
            cwd=str(repo_dir),
            timeout=300
        )
        logs.append(f"Up output:\n{out}\n{err}")
        
        if code != 0:
            raise Exception(f"Docker compose up failed: {err or out}")
        
        # Get running containers
        code, out, err = run_cmd(
            ["docker", "compose", "-p", project_name, "-f", compose_file, "ps", "--format", "table"],
            cwd=str(repo_dir)
        )
        logs.append(f"Running containers:\n{out}")
        
        app.container_id = project_name  # Store project name for compose apps
        app.status = "running"
        app.save()
        
        deployment.status = "success"
        deployment.logs = "\n".join(logs)
        deployment.finished_at = timezone.now()
        deployment.save()
        
        return Response({
            "status": "running",
            "container_id": project_name,
            "deploy_mode": "compose",
            "url": f"/{app.slug}",
            "message": f"App deployed! Access at http://YOUR_VPS_IP/{app.slug}"
        })

    def _deploy_dockerfile(self, app, deployment, repo_dir, logs):
        """Deploy app using single Dockerfile."""
        env_vars = app.env_vars or {}
        build_context = env_vars.get("_keystone_build_context", ".")
        build_dir = repo_dir / build_context if build_context != "." else repo_dir
        
        # Stop existing container if any
        container_name = f"keystone-app-{app.slug}"
        run_cmd(["docker", "stop", container_name])
        run_cmd(["docker", "rm", container_name])
        
        # Build image
        image_tag = f"keystone/{app.slug}:latest"
        logs.append(f"Building image: {image_tag} (context: {build_context})")
        
        code, out, err = run_cmd(
            ["docker", "build", "-t", image_tag, "."],
            cwd=str(build_dir),
            timeout=600
        )
        logs.append(f"Build output:\n{out}\n{err}")
        
        if code != 0:
            raise Exception(f"Docker build failed: {err or out}")
        
        # Prepare environment variables (skip internal keys)
        env_args = []
        for key, value in env_vars.items():
            if not key.startswith("_keystone_"):
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
            "deploy_mode": "dockerfile",
            "message": f"App deployed! Access at http://YOUR_VPS_IP/{app.slug}"
        })
    
    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        """Stop a running app."""
        app = self.get_object()
        env_vars = app.env_vars or {}
        deploy_mode = env_vars.get("_keystone_deploy_mode", "dockerfile")
        
        if deploy_mode == "compose":
            # Stop compose stack
            repo_dir = REPOS_DIR / app.slug
            compose_file = env_vars.get("_keystone_compose_file", "docker-compose.yml")
            project_name = f"keystone-{app.slug}"
            run_cmd(
                ["docker", "compose", "-p", project_name, "-f", compose_file, "stop"],
                cwd=str(repo_dir)
            )
        else:
            # Stop single container
            container_name = f"keystone-app-{app.slug}"
            run_cmd(["docker", "stop", container_name])
        
        app.status = "stopped"
        app.save()
        
        return Response({"status": "stopped"})
    
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """Get container logs."""
        app = self.get_object()
        env_vars = app.env_vars or {}
        deploy_mode = env_vars.get("_keystone_deploy_mode", "dockerfile")
        
        if deploy_mode == "compose":
            # Get compose logs
            repo_dir = REPOS_DIR / app.slug
            compose_file = env_vars.get("_keystone_compose_file", "docker-compose.yml")
            project_name = f"keystone-{app.slug}"
            code, out, err = run_cmd(
                ["docker", "compose", "-p", project_name, "-f", compose_file, "logs", "--tail", "100"],
                cwd=str(repo_dir)
            )
        else:
            # Get single container logs
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
