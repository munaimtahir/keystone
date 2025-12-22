from rest_framework import serializers
from .models import Repository, App, Deployment, AuditLog

class RepositorySerializer(serializers.ModelSerializer):
  github_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
  class Meta:
    model = Repository
    fields = "__all__"

class AppSerializer(serializers.ModelSerializer):
  repo_name = serializers.CharField(source="repo.name", read_only=True)
  class Meta:
    model = App
    fields = "__all__"


class DeploymentSerializer(serializers.ModelSerializer):
  app_name = serializers.CharField(source="app.name", read_only=True)
  repo_name = serializers.CharField(source="app.repo.name", read_only=True)

  class Meta:
    model = Deployment
    fields = "__all__"


class AuditLogSerializer(serializers.ModelSerializer):
  username = serializers.CharField(source="user.username", read_only=True)

  class Meta:
    model = AuditLog
    fields = "__all__"
