import time, subprocess, os
from pathlib import Path
import django
import urllib.request
import urllib.error
from urllib.parse import quote

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
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

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

def deploy_one(dep: Deployment):
    app = dep.app
    repo = app.repo

    dep.status = "running"
    dep.started_at = timezone.now()
    dep.save(update_fields=["status","started_at"])

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
        run(["docker","rm","-f",cname])
        env_flags = []
        for k, v in (app.env_vars or {}).items():
            env_flags.extend(["-e", f"{k}={v}"])
        r3 = run(["docker","run","-d","--name",cname,"-p",f"{port}:{app.container_port}"] + env_flags + [tag])

        with open(logp,"w",encoding="utf-8") as f:
            f.write("=== rollback ===\n")
            f.write(r3.stdout + r3.stderr + "\n")

        dep.logs_path=str(logp)
        if r3.returncode != 0:
            dep.status="failed"
            dep.error_summary="Rollback failed. See logs."
            app.status="failed"
        elif not _health_check(port, app.health_check_path):
            dep.status="failed"
            dep.error_summary="Health check failed after 30 seconds."
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
            with open(logp,"w",encoding="utf-8") as f:
                f.write("=== git ===\n"+r.stdout+r.stderr+"\n")
            dep.logs_path=str(logp)
            dep.status="failed"
            dep.error_summary=f"Git operation failed: {r.stderr.strip() or 'unknown error'}"
            dep.ended_at=timezone.now()
            dep.save(update_fields=["status","error_summary","ended_at","logs_path"])
            app.status="failed"
            app.save(update_fields=["status","current_port"])
            return

        tag = f"keystone/{safe}:{dep.id}"
        r2 = run(["docker","build","-t",tag,"."], cwd=str(workdir))

        run(["docker","rm","-f",cname])
        env_flags = []
        for k, v in (app.env_vars or {}).items():
            env_flags.extend(["-e", f"{k}={v}"])
        r3 = run(["docker","run","-d","--name",cname,"-p",f"{port}:{app.container_port}"] + env_flags + [tag])

        with open(logp,"w",encoding="utf-8") as f:
            f.write("=== git ===\n"+r.stdout+r.stderr+"\n")
            f.write("=== build ===\n"+r2.stdout+r2.stderr+"\n")
            f.write("=== run ===\n"+r3.stdout+r3.stderr+"\n")

        dep.logs_path=str(logp)
        if r2.returncode != 0 or r3.returncode != 0:
            dep.status="failed"
            dep.error_summary="Build or run failed. See logs."
            app.status="failed"
        elif not _health_check(port, app.health_check_path):
            dep.status="failed"
            dep.error_summary="Health check failed after 30 seconds."
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
            dep.status="failed"
            dep.error_summary=str(e)
            dep.ended_at=timezone.now()
            dep.save(update_fields=["status","error_summary","ended_at"])
            dep.app.status="failed"
            dep.app.save(update_fields=["status"])
        time.sleep(1)

if __name__ == "__main__":
    print("Runner started...")
    main()
