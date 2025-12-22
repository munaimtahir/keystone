# Keystone Complete Implementation Plan

**Goal:** Fix all bugs, complete all missing features, and align the app with documentation requirements.

**Based on:** [`AUDIT_REPORT.md`](AUDIT_REPORT.md) and [`docs/`](docs/) requirements

---

## Overview

This plan is organized into **5 phases**, prioritized by MVP criticality:

1. **Phase 1: Critical Bug Fixes** (MVP blockers)
2. **Phase 2: Core MVP Features** (logs, history, status visibility)
3. **Phase 3: Security & Authentication** (per docs requirements)
4. **Phase 4: UX Improvements** (error handling, loading states)
5. **Phase 5: Advanced Features** (health checks, update workflow, container port config)

---

## Phase 1: Critical Bug Fixes (MVP Blockers)

### 1.1 Fix Git Clone Error Checking
**File:** [`platform/backend/runner.py`](platform/backend/runner.py)  
**Issue:** Git clone/pull errors are not checked, causing cryptic failures later.

**Changes:**
- After line 49, check `r.returncode` after git clone/pull
- If `r.returncode != 0`, fail deployment immediately with clear error
- Update error_summary to include git stderr
- Save logs before failing

**Code location:** Lines 46-49, 64-67

**Implementation:**
```python
# After git clone/pull (line 49)
if r.returncode != 0:
    dep.status = "failed"
    dep.error_summary = f"Git operation failed: {r.stderr}"
    dep.ended_at = timezone.now()
    with open(logp, "w", encoding="utf-8") as f:
        f.write("=== git ===\n" + r.stdout + r.stderr + "\n")
    dep.logs_path = str(logp)
    dep.save()
    app.status = "failed"
    app.save(update_fields=["status"])
    return
```

### 1.2 Fix Port Allocation Race Condition
**File:** [`platform/backend/runner.py`](platform/backend/runner.py)  
**Issue:** Concurrent deploys can allocate the same port.

**Changes:**
- Use Django's `select_for_update()` to lock App records during port allocation
- Wrap port allocation in a transaction
- Update `allocate_port()` to use atomic operations

**Code location:** Lines 19-26, 39-40

**Implementation:**
```python
from django.db import transaction

def allocate_port(app: AppModel) -> int:
    with transaction.atomic():
        # Lock all apps to prevent concurrent allocation
        used = set(AppModel.objects.select_for_update()
                   .exclude(current_port__isnull=True)
                   .values_list("current_port", flat=True))
        for p in range(PORT_START, PORT_END+1):
            if p not in used:
                return p
    raise RuntimeError("No ports available")

# In deploy_one, wrap port assignment in transaction
with transaction.atomic():
    port = app.current_port or allocate_port(app)
    app.current_port = port
    app.save(update_fields=["current_port"])
```

### 1.3 Make Container Port Configurable
**File:** [`platform/backend/api/models.py`](platform/backend/api/models.py), [`platform/backend/runner.py`](platform/backend/runner.py)  
**Issue:** Hardcoded assumption that all containers expose :8000.

**Changes:**
- Add `container_port` field to `App` model (IntegerField, default=8000)
- Create migration for new field
- Update runner to use `app.container_port` instead of hardcoded 8000
- Update serializer to include `container_port`

**Files to modify:**
- [`platform/backend/api/models.py`](platform/backend/api/models.py) - Add field
- [`platform/backend/runner.py`](platform/backend/runner.py) - Use field (line 56)
- [`platform/backend/api/serializers.py`](platform/backend/api/serializers.py) - Include in serializer

**Implementation:**
```python
# In models.py App class
container_port = models.IntegerField(default=8000, help_text="Port the container exposes")

# In runner.py line 56
r3 = run(["docker","run","-d","--name",cname,"-p",f"{port}:{app.container_port}",tag])
```

---

## Phase 2: Core MVP Features

### 2.1 Add Deployment Logs API Endpoint
**Files:** [`platform/backend/api/views.py`](platform/backend/api/views.py), [`platform/backend/api/urls.py`](platform/backend/api/urls.py)  
**Requirement:** [`docs/WORKFLOWS.md:21-24`](docs/WORKFLOWS.md#L21-L24) - View logs

**Changes:**
- Create `DeploymentViewSet` with custom action `logs`
- Add endpoint `GET /api/deployments/:id/logs/`
- Read log file from `deployment.logs_path`
- Return log content or 404 if file doesn't exist
- Handle file read errors gracefully

**Implementation:**
```python
# In views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from pathlib import Path

class DeploymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Deployment.objects.all().order_by("-created_at")
    serializer_class = DeploymentSerializer  # Need to create this
    permission_classes = [permissions.AllowAny]  # Will change in Phase 3
    
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        deployment = self.get_object()
        if not deployment.logs_path:
            return Response({"error": "No logs available"}, status=404)
        
        log_path = Path(deployment.logs_path)
        if not log_path.exists():
            return Response({"error": "Log file not found"}, status=404)
        
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            return Response({"logs": content, "deployment_id": deployment.id})
        except Exception as e:
            return Response({"error": str(e)}, status=500)
```

**Also create:**
- [`platform/backend/api/serializers.py`](platform/backend/api/serializers.py) - Add `DeploymentSerializer`
- [`platform/backend/api/urls.py`](platform/backend/api/urls.py) - Register `DeploymentViewSet`

### 2.2 Add Deployment History Endpoint
**Files:** [`platform/backend/api/views.py`](platform/backend/api/views.py), [`platform/backend/api/urls.py`](platform/backend/api/urls.py)  
**Requirement:** [`docs/WORKFLOWS.md:21-24`](docs/WORKFLOWS.md#L21-L24) - Review deployment history

**Changes:**
- Extend `DeploymentViewSet` to support filtering by app
- Add query parameter `?app=<app_id>` to filter deployments
- Return deployments ordered by `created_at` descending
- Include app name, status, timestamps, error_summary

**Implementation:**
```python
# In DeploymentViewSet
def get_queryset(self):
    queryset = Deployment.objects.all().order_by("-created_at")
    app_id = self.request.query_params.get('app', None)
    if app_id:
        queryset = queryset.filter(app_id=app_id)
    return queryset
```

### 2.3 Add Deployment History UI
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Requirement:** Show deployment history per app

**Changes:**
- Add "View History" button/link for each app
- Fetch deployments: `GET /api/deployments/?app=<app_id>`
- Display table with: timestamp, status, error_summary, "View Logs" link
- Add modal or expandable section to show history

### 2.4 Add Deployment Logs Viewing UI
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Requirement:** View logs for troubleshooting

**Changes:**
- Add "View Logs" button in deployment history
- Fetch logs: `GET /api/deployments/:id/logs/`
- Display logs in modal or expandable section
- Format logs (monospace font, preserve whitespace)
- Show loading state while fetching

### 2.5 Add Status Polling to Frontend
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Requirement:** User should see deployment progress

**Changes:**
- After triggering deploy, start polling `/api/apps/` every 2-3 seconds
- Stop polling when status is "running", "failed", or "success"
- Update UI to show current status
- Show "Deploying..." indicator

**Implementation:**
```javascript
const [polling, setPolling] = React.useState(false)

async function deploy(id) {
  await fetch(`${api}/api/apps/${id}/deploy/`, {method:"POST"})
  setPolling(true)
  load() // Initial load
}

React.useEffect(() => {
  if (!polling) return
  const interval = setInterval(() => {
    load()
    // Stop polling if no apps are deploying
    const deploying = apps.some(a => a.status === "deploying" || a.status === "queued")
    if (!deploying) {
      setPolling(false)
      clearInterval(interval)
    }
  }, 2000)
  return () => clearInterval(interval)
}, [polling, apps])
```

---

## Phase 3: Security & Authentication

### 3.1 Add User Model & Authentication
**Files:** [`platform/backend/api/models.py`](platform/backend/api/models.py), [`platform/backend/keystone/settings.py`](platform/backend/keystone/settings.py)  
**Requirement:** [`docs/SECURITY_MODEL.md:3`](docs/SECURITY_MODEL.md#L3) - UI protected by authentication

**Changes:**
- Use Django's built-in User model (already in INSTALLED_APPS)
- Configure DRF authentication: SessionAuthentication + TokenAuthentication
- Create superuser management command or auto-create default user
- Update all ViewSets to use `IsAuthenticated` instead of `AllowAny`

**Implementation:**
```python
# In settings.py, add REST_FRAMEWORK config
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# In views.py, change all permission_classes
permission_classes = [permissions.IsAuthenticated]
```

**Also:**
- Add `rest_framework.authtoken` to INSTALLED_APPS
- Run migration: `python manage.py migrate`
- Create token endpoint or admin interface for token generation

### 3.2 Add Login UI
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Requirement:** User must authenticate to access panel

**Changes:**
- Add login form (username/password)
- POST to Django's `/admin/login/` or create custom login endpoint
- Store session/token, include in API requests
- Show login screen if not authenticated
- Add logout button

**Implementation:**
```javascript
const [authenticated, setAuthenticated] = React.useState(false)
const [username, setUsername] = React.useState("")
const [password, setPassword] = React.useState("")

async function login(e) {
  e.preventDefault()
  const formData = new FormData()
  formData.append("username", username)
  formData.append("password", password)
  
  const res = await fetch(`${api}/api/auth/login/`, {
    method: "POST",
    body: formData,
    credentials: "include"
  })
  if (res.ok) {
    setAuthenticated(true)
  }
}

// Wrap all API calls with credentials: "include" for session auth
```

**Backend:** Create login endpoint or use Django's built-in auth views

### 3.3 Add GitHub PAT Storage
**Files:** [`platform/backend/api/models.py`](platform/backend/api/models.py), [`platform/backend/runner.py`](platform/backend/runner.py)  
**Requirement:** [`docs/SECURITY_MODEL.md:4`](docs/SECURITY_MODEL.md#L4) - GitHub tokens stored server-side

**Changes:**
- Add `github_token` field to `Repository` model (CharField, blank=True)
- Encrypt token at rest (use Django's `cryptography` or `django-encrypted-model-fields`)
- Update serializer to exclude token from responses (write-only)
- Update runner to use token in git clone URL if present
- Add token input field in UI (masked input)

**Implementation:**
```python
# In models.py
from django_cryptography.fields import encrypt  # Or use simple encryption

class Repository(models.Model):
    # ... existing fields
    github_token = models.CharField(max_length=200, blank=True, help_text="GitHub PAT for private repos")
    # Or use: github_token = encrypt(models.CharField(max_length=200, blank=True))

# In runner.py, modify git clone
def get_git_url_with_auth(repo):
    if repo.github_token and "github.com" in repo.git_url:
        # Insert token into URL: https://token@github.com/user/repo.git
        url = repo.git_url.replace("https://", f"https://{repo.github_token}@")
        return url
    return repo.git_url

# Use in deploy_one:
git_url = get_git_url_with_auth(repo)
r = run(["git","clone","--depth","1","-b",repo.default_branch,git_url,str(workdir)])
```

**Alternative (simpler):** Store token in environment variable per repo, or use global GitHub token env var.

### 3.4 Add Audit Logging
**Files:** [`platform/backend/api/models.py`](platform/backend/api/models.py), [`platform/backend/api/views.py`](platform/backend/api/views.py)  
**Requirement:** [`docs/SECURITY_MODEL.md:6`](docs/SECURITY_MODEL.md#L6) - Deployment actions audited

**Changes:**
- Create `AuditLog` model (user, action, resource_type, resource_id, timestamp, details)
- Add middleware or signal handlers to log:
  - Repository creation/update/delete
  - App creation/update/delete
  - Deployment triggers
- Create endpoint to view audit logs (admin-only or authenticated users)

**Implementation:**
```python
# In models.py
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)  # "create", "update", "delete", "deploy"
    resource_type = models.CharField(max_length=50)  # "repository", "app", "deployment"
    resource_id = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

# In views.py, add logging decorator or middleware
def log_action(action, resource_type, resource_id, user, details=None):
    AuditLog.objects.create(
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {}
    )
```

---

## Phase 4: UX Improvements

### 4.1 Add Error Handling to Frontend
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Issue:** Network errors fail silently

**Changes:**
- Wrap all `fetch()` calls in try/catch
- Display error messages in UI (toast, banner, or inline)
- Show specific error messages from API responses
- Handle 401 (unauthorized) by redirecting to login

**Implementation:**
```javascript
const [error, setError] = React.useState(null)

async function load() {
  try {
    const [reposRes, appsRes] = await Promise.all([
      fetch(`${api}/api/repos/`),
      fetch(`${api}/api/apps/`)
    ])
    
    if (!reposRes.ok || !appsRes.ok) {
      throw new Error("Failed to load data")
    }
    
    setRepos(await reposRes.json())
    setApps(await appsRes.json())
    setError(null)
  } catch (e) {
    setError(e.message)
  }
}

// Display error in UI
{error && <div style={{color:"red", padding:8}}>Error: {error}</div>}
```

### 4.2 Add Loading States
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Issue:** No feedback during async operations

**Changes:**
- Add `loading` state variable
- Set loading=true before fetch, false after
- Show spinner or "Loading..." text
- Disable buttons during loading

**Implementation:**
```javascript
const [loading, setLoading] = React.useState(false)

async function deploy(id) {
  setLoading(true)
  try {
    await fetch(`${api}/api/apps/${id}/deploy/`, {method:"POST"})
    load()
  } finally {
    setLoading(false)
  }
}

// In button
<button onClick={()=>deploy(a.id)} disabled={loading}>
  {loading ? "Deploying..." : "Deploy"}
</button>
```

### 4.3 Disable Deploy Button During Deployment
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Issue:** Can trigger multiple deploys

**Changes:**
- Track which apps are currently deploying (status === "deploying" or "queued")
- Disable deploy button for those apps
- Show "Deploying..." text instead of "Deploy"

**Implementation:**
```javascript
const isDeploying = (app) => app.status === "deploying" || app.status === "queued"

// In button
<button 
  onClick={()=>deploy(a.id)} 
  disabled={isDeploying(a) || loading}
>
  {isDeploying(a) ? "Deploying..." : "Deploy"}
</button>
```

### 4.4 Improve Form Validation
**File:** [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Issue:** No validation before submitting

**Changes:**
- Validate git_url format (must be valid URL)
- Validate app name (required, unique check)
- Validate port range if manually entered
- Show validation errors inline

---

## Phase 5: Advanced Features

### 5.1 Add Health Checks for Deployed Apps
**Files:** [`platform/backend/runner.py`](platform/backend/runner.py), [`platform/backend/api/models.py`](platform/backend/api/models.py)  
**Requirement:** [`docs/DEPLOYMENT_CONVENTIONS.md:6`](docs/DEPLOYMENT_CONVENTIONS.md#L6), [`docs/WORKFLOWS.md:14`](docs/WORKFLOWS.md#L14)

**Changes:**
- Add `health_check_url` field to `App` model (optional)
- After docker run, if health_check_url is set, make HTTP GET request
- Wait up to 30 seconds for health check to pass
- Mark deployment as failed if health check fails
- Update app status based on health check result

**Implementation:**
```python
# In models.py App class
health_check_url = models.URLField(blank=True, help_text="Optional health check endpoint (e.g., /health)")

# In runner.py, after docker run
if app.health_check_url:
    import requests
    import time
    health_url = f"http://localhost:{port}{app.health_check_url}"
    max_wait = 30
    waited = 0
    while waited < max_wait:
        try:
            resp = requests.get(health_url, timeout=2)
            if resp.status_code == 200:
                break
        except:
            pass
        time.sleep(2)
        waited += 2
    else:
        # Health check failed
        dep.status = "failed"
        dep.error_summary = "Health check failed after 30 seconds"
```

### 5.2 Add Update Workflow Distinction
**Files:** [`platform/backend/api/views.py`](platform/backend/api/views.py), [`platform/frontend/src/main.jsx`](platform/frontend/src/main.jsx)  
**Requirement:** [`docs/WORKFLOWS.md:16-19`](docs/WORKFLOWS.md#L16-L19)

**Changes:**
- Add "Update" button/action separate from "Deploy"
- Update action should:
  - Pull latest changes (git pull)
  - Rebuild image
  - Restart container
  - Validate health
- Track deployment type (initial vs update) in Deployment model

**Implementation:**
```python
# In models.py Deployment
DEPLOYMENT_TYPES = [("initial", "Initial"), ("update", "Update")]
deployment_type = models.CharField(max_length=20, choices=DEPLOYMENT_TYPES, default="initial")

# In views.py, add update action
@action(detail=True, methods=["post"])
def update(self, request, pk=None):
    app = self.get_object()
    d = Deployment.objects.create(app=app, status="queued", deployment_type="update")
    # ... same as deploy but with type="update"
```

### 5.3 Add Container Status Check
**Files:** [`platform/backend/api/views.py`](platform/backend/api/views.py), [`platform/backend/runner.py`](platform/backend/runner.py)  
**Requirement:** [`docs/WORKFLOWS.md:23`](docs/WORKFLOWS.md#L23)

**Changes:**
- Add endpoint to check Docker container status
- Query Docker API to see if container is running
- Update app status if container has stopped
- Add "Check Status" button in UI

**Implementation:**
```python
# In views.py
@action(detail=True, methods=["get"])
def container_status(self, request, pk=None):
    app = self.get_object()
    if not app.current_port:
        return Response({"status": "not_deployed"})
    
    import subprocess
    cname = f"app_{app.name.replace(' ','_').lower()}"
    result = subprocess.run(["docker", "ps", "--filter", f"name={cname}", "--format", "{{.Status}}"], 
                          capture_output=True, text=True)
    
    if result.returncode == 0 and result.stdout.strip():
        return Response({"status": "running", "details": result.stdout.strip()})
    else:
        return Response({"status": "stopped"})
```

### 5.4 Add Environment Variables Support
**Files:** [`platform/backend/api/models.py`](platform/backend/api/models.py), [`platform/backend/runner.py`](platform/backend/runner.py)  
**Requirement:** [`docs/WORKFLOWS.md:7`](docs/WORKFLOWS.md#L7)

**Changes:**
- Add `env_vars` JSONField to `App` model
- Store key-value pairs of environment variables
- Pass env vars to `docker run` via `-e` flags
- Add UI form to edit env vars

**Implementation:**
```python
# In models.py App class
env_vars = models.JSONField(default=dict, blank=True, help_text="Environment variables for container")

# In runner.py, modify docker run
env_flags = []
for key, value in app.env_vars.items():
    env_flags.extend(["-e", f"{key}={value}"])

r3 = run(["docker","run","-d","--name",cname,"-p",f"{port}:{app.container_port}"] + env_flags + [tag])
```

### 5.5 Add Rollback Functionality
**Files:** [`platform/backend/api/views.py`](platform/backend/api/views.py), [`platform/backend/runner.py`](platform/backend/runner.py)  
**Requirement:** [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) (mentioned in workflows)

**Changes:**
- Track previous successful deployment's image_tag
- Add "Rollback" action that:
  - Stops current container
  - Runs previous image
  - Updates app status
- Add rollback button in UI (only show if previous deployment exists)

**Implementation:**
```python
# In views.py
@action(detail=True, methods=["post"])
def rollback(self, request, pk=None):
    app = self.get_object()
    # Find last successful deployment
    last_success = app.deployments.filter(status="success").order_by("-ended_at").first()
    if not last_success:
        return Response({"error": "No previous successful deployment"}, status=400)
    
    # Create new deployment with previous image
    d = Deployment.objects.create(
        app=app, 
        status="queued",
        deployment_type="rollback",
        image_tag=last_success.image_tag
    )
    # Runner will handle the rollback
```

---

## Implementation Order & Dependencies

### Week 1: Critical Fixes (Phase 1)
1. Fix git clone error checking (1.1)
2. Fix port allocation race condition (1.2)
3. Make container port configurable (1.3)

### Week 2: Core Features (Phase 2)
4. Add deployment logs API (2.1)
5. Add deployment history endpoint (2.2)
6. Add deployment history UI (2.3)
7. Add deployment logs viewing UI (2.4)
8. Add status polling (2.5)

### Week 3: Security (Phase 3)
9. Add authentication backend (3.1)
10. Add login UI (3.2)
11. Add GitHub PAT storage (3.3)
12. Add audit logging (3.4)

### Week 4: UX & Polish (Phase 4)
13. Add error handling (4.1)
14. Add loading states (4.2)
15. Disable deploy button (4.3)
16. Improve form validation (4.4)

### Week 5: Advanced Features (Phase 5)
17. Add health checks (5.1)
18. Add update workflow (5.2)
19. Add container status check (5.3)
20. Add environment variables (5.4)
21. Add rollback (5.5)

---

## Testing Checklist

After each phase, verify:
- [ ] Can deploy 2 different repos without conflicts
- [ ] Git errors are caught and displayed
- [ ] Port conflicts are prevented
- [ ] Deployment logs are viewable
- [ ] Deployment history is accessible
- [ ] Status updates are visible in UI
- [ ] Authentication works
- [ ] GitHub PAT works for private repos
- [ ] Error messages are shown
- [ ] Loading states work
- [ ] Health checks work (if implemented)
- [ ] Update workflow works (if implemented)

---

## Migration Strategy

1. **Database Migrations:**
   - Run `python manage.py makemigrations` after each model change
   - Run `python manage.py migrate` before deploying

2. **Backward Compatibility:**
   - New fields should have defaults or be nullable
   - Existing deployments should continue to work

3. **Deployment:**
   - Test each phase in isolation
   - Deploy incrementally
   - Monitor logs for errors

---

## Notes

- **Traefik Integration:** Deferred to Phase B (per README.md line 4-5)
- **Domain-based Routing:** Deferred to Phase B
- **TLS/HTTPS:** Deferred to Phase B
- **Multi-user/Roles:** Can be added later if needed
- **API Documentation:** Consider adding OpenAPI/Swagger docs

---

**Total Estimated Tasks:** 21 major features + migrations + testing  
**Estimated Timeline:** 5 weeks for complete implementation  
**Priority:** Phases 1-2 are MVP-critical; Phases 3-5 enhance completeness and usability

