# Keystone Deployment Report

**Date:** 2025-12-23  
**VPS:** 34.87.144.205 (GCP)  
**OS:** Ubuntu 24.04.3 LTS  
**Deployed by:** Autonomous DevOps Agent

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet (Port 80)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Traefik v3.6 (Reverse Proxy)              │
│              Listens on 0.0.0.0:80, 127.0.0.1:8080          │
│              Routes: /api → backend, / → frontend            │
└─────────────────────────────────────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌─────────────────────┐            ┌─────────────────────────┐
│  keystone-backend   │            │   keystone-frontend     │
│   Django + DRF      │            │    React + Nginx        │
│   Port 8000 (int)   │            │    Port 80 (int)        │
└─────────────────────┘            └─────────────────────────┘
           │
           ▼
┌─────────────────────┐
│   keystone-db       │
│   PostgreSQL 16     │
│   Port 5432 (int)   │
└─────────────────────┘
```

---

## 2. Deployment Details

### Containers Running

| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| keystone-traefik | traefik:v3.6 | Running | 80 (public), 8080 (localhost) |
| keystone-backend | keystone-backend | Running | 8000 (internal) |
| keystone-frontend | keystone-frontend | Running | 80 (internal) |
| keystone-db | postgres:16-alpine | Running (healthy) | 5432 (internal) |

### Access URLs

| Service | URL |
|---------|-----|
| **Keystone Panel** | http://34.87.144.205/ |
| **API Health Check** | http://34.87.144.205/api/health/ |
| **Traefik Dashboard** | http://127.0.0.1:8080/ (localhost only) |

### Credentials

| Service | Username | Password |
|---------|----------|----------|
| Keystone Admin | admin | `72mGn40eW4YH3uba` |
| PostgreSQL | keystone | `A9TO312Br161u4OHbnN7Gsuk` |

> ⚠️ **Security Note:** Change these credentials in production! They are stored in `/home/munaim/keystone/repos/keystone/.env`

---

## 3. How to Operate

### View Logs

```bash
cd /home/munaim/keystone/repos/keystone

# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f traefik
docker compose logs -f db
```

### Restart Services

```bash
cd /home/munaim/keystone/repos/keystone

# Restart all
docker compose restart

# Restart specific service
docker compose restart backend
```

### Redeploy (with rebuild)

```bash
cd /home/munaim/keystone/repos/keystone
docker compose up -d --build
```

### Rollback

```bash
cd /home/munaim/keystone/repos/keystone

# View previous images
docker images | grep keystone

# Rollback to previous commit
git checkout main  # or specific commit
docker compose up -d --build
```

### Stop All Services

```bash
cd /home/munaim/keystone/repos/keystone
docker compose down
```

### Full Cleanup (including volumes)

```bash
cd /home/munaim/keystone/repos/keystone
docker compose down -v  # ⚠️ This deletes the database!
```

---

## 4. Database

### Connection Info

- **Host:** db (internal Docker network)
- **Port:** 5432
- **Database:** keystone
- **User:** keystone

### Access PostgreSQL

```bash
docker exec -it keystone-db psql -U keystone -d keystone
```

### Backup Database

```bash
docker exec keystone-db pg_dump -U keystone keystone > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
cat backup.sql | docker exec -i keystone-db psql -U keystone -d keystone
```

---

## 5. Configuration Files

| File | Purpose |
|------|---------|
| `/home/munaim/keystone/repos/keystone/.env` | Environment variables (secrets) |
| `/home/munaim/keystone/repos/keystone/docker-compose.yml` | Docker Compose configuration |
| `/home/munaim/keystone/repos/keystone/platform/backend/keystone/settings.py` | Django settings |
| `/home/munaim/keystone/repos/keystone/platform/frontend/nginx.conf` | Nginx configuration |

---

## 6. Monitoring

### Health Check

```bash
curl http://34.87.144.205/api/health/
# Expected: {"status":"ok","service":"keystone"}
```

### Container Status

```bash
docker compose ps
```

### Resource Usage

```bash
docker stats --no-stream
```

---

## 7. Files Changed in This Deployment

| File | Change |
|------|--------|
| `docker-compose.yml` | Updated Traefik v3.2 → v3.6, secured dashboard to localhost |
| `platform/frontend/src/components/AppDetail.jsx` | Fixed JSX syntax error |
| `.env` | Created with secure random credentials |

---

## 8. Next Steps (Recommendations)

1. **Add HTTPS/TLS** - Configure Let's Encrypt via Traefik for production
2. **Change default credentials** - Update admin password via the UI
3. **Configure backups** - Set up automated PostgreSQL backups
4. **Add monitoring** - Consider Prometheus/Grafana for metrics
5. **Review firewall** - Consider closing port 8080 externally if not needed

