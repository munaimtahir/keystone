import time, subprocess, os
from pathlib import Path
import django
import urllib.request
import urllib.error
from urllib.parse import quote
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "keystone.settings")
django.setup()

from django.utils import timezone
from api.models import Deployment
from api.models import App as AppModel
from django.db import transaction

PORT_START = int(os.getenv("PORT_RANGE_START", "9000"))
PORT_END = int(os.getenv("PORT_RANGE_END", "9999"))
REPOS_DIR = Path("/runtime/repos"); REPOS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = Path("/runtime/logs"); LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Simple in-DB port reservation (MVP)
def allocate_port(app: AppModel) -> int:
    # Must be called inside an outer transaction.atomic() to avoid races.
    used = set(
        AppModel.objects.select_for_update()
        .exclude(current_port__isnull=True)
        .values_list("current_port", flat=True)
    )
    for p in range(PORT_START, PORT_END+1):
        if p not in used:
            return p
    raise RuntimeError("No ports available")

def run(cmd, cwd=None):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        # Create a mock result object for missing commands
        result = subprocess.CompletedProcess(cmd, 1, "", f"Command not found: {cmd[0] if cmd else 'unknown'}. Error: {str(e)}")
        return result

def _container_name(app: AppModel) -> str:
    safe = app.name.replace(" ","_").lower()
    return f"app_{safe}"

def _git_url(repo) -> str:
    url = repo.git_url
    token = (getattr(repo, "github_token", "") or "").strip()
    if token and url.startswith("https://") and "github.com" in url:
        return url.replace("https://", f"https://x-access-token:{quote(token, safe='')}@")
    return url

def _health_check(port: int, path: str) -> bool:
    path = (path or "").strip()
    if not path:
        return True
    if not path.startswith("/"):
        path = "/" + path
    url = f"http://127.0.0.1:{port}{path}"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass
        time.sleep(2)
    return False

def _check_docker_available():
    """Check if docker command is available."""
    try:
        # Try 'docker' first
        result = subprocess.run(["which", "docker"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    
    try:
        # Try 'docker.io' (some Debian/Ubuntu installations)
        result = subprocess.run(["which", "docker.io"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    
    # Try common docker paths
    for path in ["/usr/bin/docker", "/usr/bin/docker.io", "/usr/local/bin/docker"]:
        if os.path.exists(path):
            return path
    
    return None

def deploy_one(dep: Deployment):
    app = dep.app
    repo = app.repo

    dep.status = "deploying"
    dep.started_at = timezone.now()
    dep.save(update_fields=["status","started_at"])
    
    # Check docker availability early
    docker_cmd = _check_docker_available()
    if not docker_cmd:
        logp = LOGS_DIR / f"deploy_{dep.id}.log"
        with open(logp, "w", encoding="utf-8") as f:
            f.write("=== error ===\n")
            f.write("Docker command not found. Please ensure docker is installed and in PATH.\n")
        dep.logs_path = str(logp)
        dep.status = "failed"
        dep.error_summary = "Docker command not found. The runner cannot execute docker commands."
        dep.ended_at = timezone.now()
        dep.save(update_fields=["status", "error_summary", "ended_at", "logs_path"])
        app.status = "failed"
        app.save(update_fields=["status"])
        return

    # Allocate/lock port in a transaction to avoid concurrent assignment.
    with transaction.atomic():
        app_locked = AppModel.objects.select_for_update().get(pk=app.pk)
        port = app_locked.current_port or allocate_port(app_locked)
        app_locked.current_port = port
        app_locked.save(update_fields=["current_port"])
        port = app_locked.current_port
        app.current_port = port

    safe = app.name.replace(" ","_").lower()
    workdir = REPOS_DIR / safe
    logp = LOGS_DIR / f"deploy_{dep.id}.log"

    cname = _container_name(app)

    # Rollback deployments skip git/build and just run the prior image tag.
    if getattr(dep, "deployment_type", "initial") == "rollback":
        tag = dep.image_tag
        run([docker_cmd,"rm","-f",cname])
        env_flags = []
        for k, v in (app.env_vars or {}).items():
            env_flags.extend(["-e", f"{k}={v}"])
        r3 = run([docker_cmd,"run","-d","--name",cname,"-p",f"{port}:{app.container_port}"] + env_flags + [tag])

        with open(logp,"w",encoding="utf-8") as f:
            f.write("=== rollback ===\n")
            f.write(r3.stdout + r3.stderr + "\n")

        dep.logs_path=str(logp)
        if r3.returncode != 0:
            dep.status="failed"
            run_error = r3.stderr.strip() or r3.stdout.strip() or "unknown run error"
            dep.error_summary=f"Rollback failed: {run_error[:200]}"
            app.status="failed"
        elif not _health_check(port, app.health_check_path):
            dep.status="failed"
            health_path = app.health_check_path or "/"
            dep.error_summary=f"Health check failed: App did not respond at http://127.0.0.1:{port}{health_path} within 30 seconds"
            app.status="failed"
        else:
            dep.status="success"
            dep.assigned_port=port
            app.status="running"

    else:
        if not workdir.exists():
            r = run(["git","clone","--depth","1","-b",repo.default_branch,_git_url(repo),str(workdir)])
        else:
            r = run(["git","pull"], cwd=str(workdir))

        # Fail fast on git errors, saving logs first.
        if r.returncode != 0:
            error_msg = r.stderr.strip() or r.stdout.strip() or "unknown error"
            with open(logp,"w",encoding="utf-8") as f:
                f.write("=== git ===\n")
                f.write(f"Command: git {'clone' if not workdir.exists() else 'pull'}\n")
                f.write(f"Return code: {r.returncode}\n")
                f.write(f"Stdout: {r.stdout}\n")
                f.write(f"Stderr: {r.stderr}\n")
            dep.logs_path=str(logp)
            dep.status="failed"
            dep.error_summary=f"Git operation failed: {error_msg}"
            dep.ended_at=timezone.now()
            dep.save(update_fields=["status","error_summary","ended_at","logs_path"])
            app.status="failed"
            app.save(update_fields=["status","current_port"])
            return

        tag = f"keystone/{safe}:{dep.id}"
        r2 = run([docker_cmd,"build","-t",tag,"."], cwd=str(workdir))

        run([docker_cmd,"rm","-f",cname])
        env_flags = []
        for k, v in (app.env_vars or {}).items():
            env_flags.extend(["-e", f"{k}={v}"])
        r3 = run([docker_cmd,"run","-d","--name",cname,"-p",f"{port}:{app.container_port}"] + env_flags + [tag])

        with open(logp,"w",encoding="utf-8") as f:
            f.write("=== git ===\n"+r.stdout+r.stderr+"\n")
            f.write("=== build ===\n"+r2.stdout+r2.stderr+"\n")
            f.write("=== run ===\n"+r3.stdout+r3.stderr+"\n")

        dep.logs_path=str(logp)
        if r2.returncode != 0:
            dep.status="failed"
            build_error = r2.stderr.strip() or r2.stdout.strip() or "unknown build error"
            # Check for common docker errors (preserve original error message for output)
            if "Cannot connect to the Docker daemon" in build_error or "permission denied" in build_error.lower():
                error_summary = f"Docker daemon connection issue: {build_error[:150]}"
            else:
                error_summary = f"Docker build failed: {build_error[:200]}"
            dep.error_summary = error_summary
            app.status="failed"
        elif r3.returncode != 0:
            dep.status="failed"
            run_error = r3.stderr.strip() or r3.stdout.strip() or "unknown run error"
            # Check for common docker errors (preserve original error message for output)
            if "Cannot connect to the Docker daemon" in run_error or "permission denied" in run_error.lower():
                error_summary = f"Docker daemon connection issue: {run_error[:150]}"
            else:
                error_summary = f"Docker run failed: {run_error[:200]}"
            dep.error_summary = error_summary
            app.status="failed"
        elif not _health_check(port, app.health_check_path):
            dep.status="failed"
            health_path = app.health_check_path or "/"
            dep.error_summary=f"Health check failed: App did not respond at http://127.0.0.1:{port}{health_path} within 30 seconds"
            app.status="failed"
        else:
            dep.status="success"
            dep.image_tag=tag
            dep.assigned_port=port
            app.status="running"

    dep.ended_at=timezone.now()
    dep.save()
    app.save(update_fields=["status","current_port"])

def main():
    while True:
        dep = Deployment.objects.filter(status="queued").order_by("id").first()
        if not dep:
            time.sleep(2); continue
        try:
            deploy_one(dep)
        except Exception as e:
            error_details = str(e)
            error_traceback = traceback.format_exc()
            
            # Always write error to log file if deployment exists
            if dep and dep.id:
                logp = LOGS_DIR / f"deploy_{dep.id}.log"
                try:
                    # Ensure log file exists, append if it does
                    mode = "a" if logp.exists() else "w"
                    with open(logp, mode, encoding="utf-8") as f:
                        if mode == "w":
                            f.write("=== exception ===\n")
                        else:
                            f.write("\n=== exception ===\n")
                        f.write(error_traceback + "\n")
                    dep.logs_path = str(logp)
                except Exception as log_error:
                    # If we can't write logs, at least try to save the error
                    print(f"Failed to write log file: {log_error}")
            
            dep.status = "failed"
            # Truncate error message at word boundary to avoid cutting mid-word
            max_error_length = 500
            error_summary_details = error_details
            if len(error_summary_details) > max_error_length:
                truncated = error_summary_details[:max_error_length]
                last_space = truncated.rfind(" ")
                if last_space != -1:
                    error_summary_details = truncated[:last_space].rstrip() + "..."
                else:
                    error_summary_details = truncated.rstrip() + "..."
            dep.error_summary = f"Deployment failed: {error_summary_details}"
            dep.ended_at = timezone.now()
            dep.save(update_fields=["status", "error_summary", "ended_at", "logs_path"])
            # Safety check for dep.app accessibility
            if dep.app is not None:
                dep.app.status = "failed"
                dep.app.save(update_fields=["status"])
        time.sleep(1)

if __name__ == "__main__":
    print("Runner started...")
    main()
