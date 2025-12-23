# Generated migration for Keystone
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='App',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique app name (used in URL path)', max_length=100, unique=True)),
                ('git_url', models.URLField(help_text='GitHub repository URL')),
                ('branch', models.CharField(default='main', max_length=100)),
                ('status', models.CharField(choices=[('imported', 'Imported'), ('preparing', 'Preparing'), ('prepared', 'Prepared'), ('deploying', 'Deploying'), ('running', 'Running'), ('stopped', 'Stopped'), ('failed', 'Failed')], default='imported', max_length=20)),
                ('error_message', models.TextField(blank=True, default='')),
                ('container_port', models.IntegerField(default=8000, help_text='Port the app listens on inside container')),
                ('env_vars', models.JSONField(blank=True, default=dict, help_text='Environment variables')),
                ('traefik_rule', models.CharField(blank=True, default='', max_length=500)),
                ('container_id', models.CharField(blank=True, default='', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Deployment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(default='pending', max_length=20)),
                ('logs', models.TextField(blank=True, default='')),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('app', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deployments', to='api.app')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
