import time, subprocess, os
from pathlib import Path
import django

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
    from api.models import Deployment  # avoid circular
    # naive scan of existing app ports
    used = set(AppModel.objects.exclude(current_port__isnull=True).values_list("current_port", flat=True))
    for p in range(PORT_START, PORT_END+1):
        if p not in used:
            return p
    raise RuntimeError("No ports available")

def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

def deploy_one(dep: Deployment):
    app = dep.app
    repo = app.repo

    dep.status = "running"
    dep.started_at = timezone.now()
    dep.save(update_fields=["status","started_at"])

    port = app.current_port or allocate_port(app)
    app.current_port = port

    safe = app.name.replace(" ","_").lower()
    workdir = REPOS_DIR / safe
    logp = LOGS_DIR / f"deploy_{dep.id}.log"

    if not workdir.exists():
        r = run(["git","clone","--depth","1","-b",repo.default_branch,repo.git_url,str(workdir)])
    else:
        r = run(["git","pull"], cwd=str(workdir))

    tag = f"keystone/{safe}:{dep.id}"
    r2 = run(["docker","build","-t",tag,"."], cwd=str(workdir))

    cname = f"app_{safe}"
    run(["docker","rm","-f",cname])
    r3 = run(["docker","run","-d","--name",cname,"-p",f"{port}:8000",tag])

    with open(logp,"w",encoding="utf-8") as f:
        f.write("=== git ===\n"+r.stdout+r.stderr+"\n")
        f.write("=== build ===\n"+r2.stdout+r2.stderr+"\n")
        f.write("=== run ===\n"+r3.stdout+r3.stderr+"\n")

    dep.logs_path=str(logp)
    if r2.returncode != 0 or r3.returncode != 0:
        dep.status="failed"
        dep.error_summary="Build or run failed. See logs."
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
