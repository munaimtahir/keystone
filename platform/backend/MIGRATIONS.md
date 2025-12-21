# Backend Database Migrations

## Overview

This document describes the database migrations for the Keystone backend API.

## Migration Status

The following migrations have been created and verified:

### api/migrations/0001_initial.py
- **Created**: 2025-12-21
- **Description**: Initial migration for the API app
- **Models**:
  - `Repository`: Stores Git repository information
  - `App`: Represents applications to be deployed
  - `Deployment`: Tracks deployment history and status

## Database Schema

### Repository Model
- `id`: Auto-incrementing primary key
- `name`: Repository name (max 120 chars)
- `git_url`: Git repository URL
- `default_branch`: Default branch name (default: "main")

### App Model
- `id`: Auto-incrementing primary key
- `name`: Application name (unique, max 120 chars)
- `repo`: Foreign key to Repository
- `access_mode`: Either "PORT" or "HOST" (default: "PORT")
- `current_port`: Currently assigned port number (nullable)
- `status`: Current application status (default: "draft")

### Deployment Model
- `id`: Auto-incrementing primary key
- `app`: Foreign key to App
- `status`: Deployment status (default: "queued")
- `image_tag`: Docker image tag (max 200 chars)
- `assigned_port`: Port assigned for this deployment (nullable)
- `created_at`: Timestamp when deployment was created
- `started_at`: Timestamp when deployment started (nullable)
- `ended_at`: Timestamp when deployment ended (nullable)
- `error_summary`: Error message if deployment failed
- `logs_path`: Path to deployment logs

## Relationships

- `Repository` has many `Apps` (one-to-many via `apps` related name)
- `App` belongs to one `Repository` (many-to-one via `repo` field)
- `App` has many `Deployments` (one-to-many via `deployments` related name)
- `Deployment` belongs to one `App` (many-to-one via `app` field)

## Verification

To verify the migrations are working correctly, run:

```bash
python3 manage.py showmigrations
python3 manage.py migrate
python3 verify_migrations.py
```

The `verify_migrations.py` script tests:
1. Migrations exist and can be applied
2. Models can be created successfully
3. Relationships between models work correctly
4. Django system check passes

## Running Migrations in Production

When deploying with Docker, migrations are automatically applied via the Dockerfile CMD:

```bash
python manage.py migrate && python manage.py runserver 0.0.0.0:8000
```

This ensures the database schema is up-to-date before the server starts.

## Troubleshooting

### Missing migrations
If you see "No migrations to apply", this is expected if the database is already up-to-date.

### Migration conflicts
If you encounter migration conflicts, use:
```bash
python3 manage.py showmigrations
python3 manage.py migrate --fake-initial
```

### Checking for unapplied migrations
```bash
python3 manage.py showmigrations | grep "\[ \]"
```

### Creating new migrations
After modifying models, always generate migrations:
```bash
python3 manage.py makemigrations
```

Then review the generated migration file before committing.
