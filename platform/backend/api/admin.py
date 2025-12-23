from django.contrib import admin
from .models import App, Deployment


@admin.register(App)
class AppAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'git_url', 'branch', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'git_url']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'app', 'status', 'created_at', 'finished_at']
    list_filter = ['status', 'created_at']
    search_fields = ['app__name']
    readonly_fields = ['created_at']
