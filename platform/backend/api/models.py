from django.db import models

class Repository(models.Model):
    name = models.CharField(max_length=120)
    git_url = models.URLField()
    default_branch = models.CharField(max_length=120, default="main")
    def __str__(self): return self.name

class App(models.Model):
    ACCESS_MODES = [("PORT","PORT"),("HOST","HOST")]
    name = models.CharField(max_length=120, unique=True)
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="apps")
    access_mode = models.CharField(max_length=10, choices=ACCESS_MODES, default="PORT")
    current_port = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="draft")
    def __str__(self): return self.name

class Deployment(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name="deployments")
    status = models.CharField(max_length=20, default="queued")
    image_tag = models.CharField(max_length=200, blank=True, default="")
    assigned_port = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    error_summary = models.TextField(blank=True, default="")
    logs_path = models.CharField(max_length=255, blank=True, default="")
