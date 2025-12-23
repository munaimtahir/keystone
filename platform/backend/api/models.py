"""
Keystone Models - Simple VPS Deployment

3-step workflow:
1. Import Repo - Add GitHub URL
2. Prepare - Configure for Traefik
3. Deploy - Run the app
"""
from django.db import models


class App(models.Model):
    """An application to deploy from GitHub."""
    
    STATUS_CHOICES = [
        ("imported", "Imported"),
        ("preparing", "Preparing"),
        ("prepared", "Prepared"),
        ("deploying", "Deploying"),
        ("running", "Running"),
        ("stopped", "Stopped"),
        ("failed", "Failed"),
    ]
    
    # Basic info
    name = models.CharField(max_length=100, unique=True, help_text="Unique app name (used in URL path)")
    git_url = models.URLField(help_text="GitHub repository URL")
    branch = models.CharField(max_length=100, default="main")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="imported")
    error_message = models.TextField(blank=True, default="")
    
    # Deployment config (set during prepare)
    container_port = models.IntegerField(default=8000, help_text="Port the app listens on inside container")
    env_vars = models.JSONField(default=dict, blank=True, help_text="Environment variables")
    
    # Traefik routing (set during prepare)
    traefik_rule = models.CharField(max_length=500, blank=True, default="")
    
    # Runtime info
    container_id = models.CharField(max_length=100, blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    @property
    def slug(self):
        """URL-safe name for routing."""
        return self.name.lower().replace(" ", "-").replace("_", "-")


class Deployment(models.Model):
    """Deployment history for an app."""
    
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name="deployments")
    status = models.CharField(max_length=20, default="pending")
    logs = models.TextField(blank=True, default="")
    error = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.app.name} - {self.status} - {self.created_at}"
