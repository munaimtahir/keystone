# Keystone Deployment Commands Log

**Date:** 2025-12-23  
**VPS:** 34.87.144.205

---

## 1. VPS Assessment

```bash
# System info
uname -a
# Output: Linux vps.asia-southeast1-a.c.cloud-app-testing-481819.internal 6.14.0-1021-gcp

cat /etc/os-release | head -5
# Output: Ubuntu 24.04.3 LTS

# Resources
nproc                    # 2 CPUs
free -h                  # 7.8GB RAM, 5.7GB available
df -h /                  # 96GB disk, 92GB free

# Docker
docker --version         # Docker version 29.1.3
docker compose version   # Docker Compose version v5.0.0

# Ports check
sudo ss -tlnp | grep -E ':80|:443|:8080'
# Output: No relevant ports in use (clean state)

# Existing containers
docker ps -a             # Empty (no containers)
```

---

## 2. Environment Setup

```bash
cd /home/munaim/keystone/repos/keystone

# Generate secure credentials
DJANGO_SECRET=$(openssl rand -base64 48 | tr -d '/+=' | head -c 64)
POSTGRES_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 16)

# Create .env file
cat > .env << EOF
# Keystone Production Configuration
POSTGRES_DB=keystone
POSTGRES_USER=keystone
POSTGRES_PASSWORD=${POSTGRES_PASS}
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=0
KEYSTONE_ADMIN_USERNAME=admin
KEYSTONE_ADMIN_PASSWORD=${ADMIN_PASS}
EOF

# Secure .env permissions
chmod 600 .env
```

---

## 3. Initial Deployment (Failed)

```bash
docker compose up -d --build
# ERROR: Frontend build failed
# /app/src/components/AppDetail.jsx:240:87: ERROR: Expected "}" but found ":"
```

---

## 4. Fix JSX Syntax Error

```bash
# Fixed line 240 in platform/frontend/src/components/AppDetail.jsx
# Changed: {"key": "value"}
# To: {`{"key": "value"}`}
```

---

## 5. Second Deployment (Traefik API Error)

```bash
docker compose up -d --build
# Containers started but Traefik showed:
# ERROR: client version 1.24 is too old. Minimum supported API version is 1.44
```

---

## 6. Fix Traefik Version

```bash
# Updated docker-compose.yml
# Changed: traefik:v3.2
# To: traefik:v3.6

docker compose up -d traefik
# SUCCESS: Traefik started without errors
```

---

## 7. Verify Deployment

```bash
# Check container status
docker compose ps
# All 4 containers running

# Test endpoints
curl -s http://localhost/api/health/
# {"status":"ok","service":"keystone"}

curl -s http://localhost/
# HTML returned (frontend working)

# Test public access
curl -s http://34.87.144.205/api/health/
# {"status":"ok","service":"keystone"}
```

---

## 8. Authentication Testing

```bash
# Login
TOKEN=$(curl -sf -X POST http://localhost/api/auth/login/ \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"72mGn40eW4YH3uba"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")

# Test authenticated endpoint
curl -s http://localhost/api/apps/ -H "Authorization: Token $TOKEN"
# []
```

---

## 9. CRUD Testing

```bash
# Create app
curl -sf -X POST http://localhost/api/apps/ \
    -H "Authorization: Token $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name": "test-app", "git_url": "https://github.com/example/repo.git", "branch": "main"}'

# Get app
curl -sf http://localhost/api/apps/1/ -H "Authorization: Token $TOKEN"

# Update app
curl -sf -X PATCH http://localhost/api/apps/1/ \
    -H "Authorization: Token $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"container_port": 5000}'

# Delete app
curl -sf -X DELETE http://localhost/api/apps/1/ -H "Authorization: Token $TOKEN"
```

---

## 10. Security Hardening

```bash
# Secure Traefik dashboard to localhost only
# Updated docker-compose.yml:
# Changed: "8080:8080"
# To: "127.0.0.1:8080:8080"

docker compose up -d traefik

# Verify
sudo ss -tlnp | grep 8080
# LISTEN 127.0.0.1:8080 (localhost only)

# Secure .env permissions
chmod 600 .env
```

---

## 11. Git Commit

```bash
git checkout -b deployment-fixes-2025-12-23
git add -A
git commit -m "fix: deployment compatibility and security improvements"
```

---

## 12. Useful Ongoing Commands

```bash
# View logs
docker compose logs -f backend

# Restart services
docker compose restart

# Rebuild and redeploy
docker compose up -d --build

# Database backup
docker exec keystone-db pg_dump -U keystone keystone > backup.sql

# Access database
docker exec -it keystone-db psql -U keystone -d keystone

# Check resource usage
docker stats --no-stream

# View Traefik routers
curl -s http://localhost:8080/api/http/routers | python3 -m json.tool
```

