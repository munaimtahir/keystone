# Keystone Backend - Django API Server
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

# Run migrations, create admin, and start server
CMD ["sh", "-c", "python manage.py migrate && python manage.py bootstrap_admin && python manage.py runserver 0.0.0.0:8000"]
