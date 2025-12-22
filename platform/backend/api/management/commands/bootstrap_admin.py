import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings


class Command(BaseCommand):
    help = "Create an initial admin user if none exists (for IP-mode MVP bootstrap)."

    def handle(self, *args, **options):  # noqa: ARG002
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("bootstrap_admin: superuser already exists, skipping.")
            return

        username = os.getenv("KEYSTONE_ADMIN_USERNAME", "admin").strip() or "admin"
        password = os.getenv("KEYSTONE_ADMIN_PASSWORD", "").strip()
        email = os.getenv("KEYSTONE_ADMIN_EMAIL", "admin@example.com").strip()

        if not password:
            # In DEBUG/dev we allow a predictable default; in prod require env var.
            if getattr(settings, "DEBUG", False):
                password = "admin"
            else:
                self.stderr.write("bootstrap_admin: KEYSTONE_ADMIN_PASSWORD is required when DEBUG=0")
                return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(f"bootstrap_admin: created superuser '{username}'")


