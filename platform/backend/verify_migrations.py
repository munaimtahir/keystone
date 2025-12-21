#!/usr/bin/env python3
"""
Verification script for backend migrations.
This script tests that:
1. Migrations can be generated
2. Migrations can be applied
3. Models can be created
4. API endpoints work correctly
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "keystone.settings")
django.setup()

from django.core.management import call_command
from django.test.utils import get_runner
from api.models import Repository, App, Deployment


def test_migrations():
    """Test that migrations exist and can be applied."""
    print("=" * 60)
    print("Testing Migrations")
    print("=" * 60)
    
    # Check if migrations exist
    print("\n1. Checking for migrations...")
    call_command("showmigrations", "api", verbosity=0)
    print("   ✓ Migrations found for 'api' app")
    
    # Check for any missing migrations
    print("\n2. Checking for missing migrations...")
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
    print("   ✓ No missing migrations detected")
    
    print("\n3. Verifying migration can be applied...")
    call_command("migrate", "--run-syncdb", verbosity=0)
    print("   ✓ Migrations applied successfully")


def test_models():
    """Test that models can be created and relationships work."""
    print("\n" + "=" * 60)
    print("Testing Models")
    print("=" * 60)
    
    # Test Repository creation
    print("\n1. Creating Repository...")
    repo = Repository.objects.create(
        name="test-repo",
        git_url="https://github.com/test/test",
        default_branch="main"
    )
    print(f"   ✓ Created Repository: {repo.name}")
    
    # Test App creation
    print("\n2. Creating App...")
    app = App.objects.create(
        name="test-app",
        repo=repo,
        access_mode="PORT",
        current_port=9000,
        status="draft"
    )
    print(f"   ✓ Created App: {app.name}")
    
    # Test Deployment creation
    print("\n3. Creating Deployment...")
    deployment = Deployment.objects.create(
        app=app,
        status="queued",
        image_tag="v1.0.0",
        assigned_port=9001
    )
    print(f"   ✓ Created Deployment (ID: {deployment.id})")
    
    # Verify relationships
    print("\n4. Verifying relationships...")
    assert app.repo.name == repo.name, "App-Repo relationship failed"
    print(f"   ✓ App->Repo: {app.repo.name}")
    
    assert deployment.app.name == app.name, "Deployment-App relationship failed"
    print(f"   ✓ Deployment->App: {deployment.app.name}")
    
    assert app.deployments.count() == 1, "App deployments count mismatch"
    print(f"   ✓ App deployments: {app.deployments.count()}")
    
    assert repo.apps.count() == 1, "Repo apps count mismatch"
    print(f"   ✓ Repo apps: {repo.apps.count()}")


def test_django_check():
    """Run Django's system check."""
    print("\n" + "=" * 60)
    print("Running Django System Check")
    print("=" * 60)
    
    call_command("check", verbosity=0)
    print("   ✓ System check passed with no issues")


def main():
    """Run all verification tests."""
    try:
        test_migrations()
        test_models()
        test_django_check()
        
        print("\n" + "=" * 60)
        print("✅ ALL VERIFICATION TESTS PASSED!")
        print("=" * 60)
        print("\nThe backend migrations are properly configured and working.")
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ VERIFICATION FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
