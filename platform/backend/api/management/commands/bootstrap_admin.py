"""Create default admin user if none exists."""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create initial admin user"

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Admin already exists, skipping.")
            return
        
        username = os.getenv("KEYSTONE_ADMIN_USERNAME", "admin")
        password = os.getenv("KEYSTONE_ADMIN_PASSWORD", "admin")
        email = os.getenv("KEYSTONE_ADMIN_EMAIL", "admin@example.com")
        
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(f"Created admin user: {username}")
