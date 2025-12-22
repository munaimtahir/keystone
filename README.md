# Keystone (IP Mode MVP)

Internal deployment control plane for a single VM (Ubuntu 24.04).  
**Phase A (now):** Access by **IP + ports** (no domain, no TLS).  
**Phase B (later):** Add **Traefik + subdomains + HTTPS**.

## Quick start (VM)
1) Install Docker + Docker Compose v2  
2) `cp env.example .env`  
3) `docker compose up -d --build`  
4) Open:
- Panel: `http://<VM_IP>:8080`
- API health: `http://<VM_IP>:8000/api/health`

## Login
Keystone uses **token authentication** for the UI/API.

- Default credentials (when `DJANGO_DEBUG=1`): **`admin / admin`**
- Production: set `KEYSTONE_ADMIN_USERNAME`, `KEYSTONE_ADMIN_PASSWORD`, `KEYSTONE_ADMIN_EMAIL` in your environment.

## App access (IP mode)
Deployed apps: `http://<VM_IP>:<assigned_port>` where port is **9000–9999**.
