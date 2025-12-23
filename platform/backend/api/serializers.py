from rest_framework import serializers
from .models import App, Deployment


class AppSerializer(serializers.ModelSerializer):
    slug = serializers.ReadOnlyField()
    
    class Meta:
        model = App
        fields = "__all__"


class DeploymentSerializer(serializers.ModelSerializer):
    app_name = serializers.CharField(source="app.name", read_only=True)
    
    class Meta:
        model = Deployment
        fields = "__all__"
