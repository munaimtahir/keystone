# Generated migration for inspection and preparation features

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_app_container_port_app_env_vars_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='prepared_for_deployment',
            field=models.BooleanField(default=False, help_text='Whether repo has been inspected and prepared for deployment'),
        ),
        migrations.AddField(
            model_name='repository',
            name='deployment_config',
            field=models.JSONField(blank=True, default=dict, help_text='Standardized deployment configuration'),
        ),
        migrations.AddField(
            model_name='repository',
            name='inspection_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('inspecting', 'Inspecting'), ('ready', 'Ready'), ('failed', 'Failed')],
                default='pending',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='repository',
            name='inspection_details',
            field=models.JSONField(blank=True, default=dict, help_text='Details from inspection process'),
        ),
        migrations.AddField(
            model_name='repository',
            name='last_inspected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

