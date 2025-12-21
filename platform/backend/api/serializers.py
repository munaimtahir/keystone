from rest_framework import serializers
from .models import Repository, App

class RepositorySerializer(serializers.ModelSerializer):
  class Meta:
    model = Repository
    fields = "__all__"

class AppSerializer(serializers.ModelSerializer):
  repo_name = serializers.CharField(source="repo.name", read_only=True)
  class Meta:
    model = App
    fields = "__all__"
