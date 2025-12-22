from django.db import models
from django.conf import settings

from .encrypted_fields import EncryptedTextField

class Repository(models.Model):
    name = models.CharField(max_length=120)
    git_url = models.URLField()
    default_branch = models.CharField(max_length=120, default="main")
    github_token = EncryptedTextField(blank=True, default="", help_text="GitHub PAT for private repos (encrypted at rest)")
    def __str__(self): return self.name

class App(models.Model):
    ACCESS_MODES = [("PORT","PORT"),("HOST","HOST")]
    name = models.CharField(max_length=120, unique=True)
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="apps")
    access_mode = models.CharField(max_length=10, choices=ACCESS_MODES, default="PORT")
    current_port = models.IntegerField(null=True, blank=True)
    container_port = models.IntegerField(default=8000, help_text="Port the container exposes")
    health_check_path = models.CharField(max_length=200, blank=True, default="", help_text="Optional health check path (e.g., /health)")
    env_vars = models.JSONField(default=dict, blank=True, help_text="Environment variables for container")
    status = models.CharField(max_length=20, default="draft")
    def __str__(self): return self.name

class Deployment(models.Model):
    DEPLOYMENT_TYPES = [("initial", "Initial"), ("update", "Update"), ("rollback", "Rollback")]
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name="deployments")
    status = models.CharField(max_length=20, default="queued")
    deployment_type = models.CharField(max_length=20, choices=DEPLOYMENT_TYPES, default="initial")
    image_tag = models.CharField(max_length=200, blank=True, default="")
    assigned_port = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    error_summary = models.TextField(blank=True, default="")
    logs_path = models.CharField(max_length=255, blank=True, default="")


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50)
    resource_type = models.CharField(max_length=50)
    resource_id = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp", "-id"]
