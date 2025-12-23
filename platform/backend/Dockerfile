# Keystone Backend - Django API Server
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including Docker CLI and Compose plugin
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (not full docker.io, just the CLI)
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.0.3.tgz | tar xz -C /usr/local/bin --strip-components=1 docker/docker

# Install Docker Compose plugin
RUN mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -fsSL https://github.com/docker/compose/releases/download/v2.29.1/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

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
