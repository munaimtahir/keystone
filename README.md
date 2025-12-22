# Keystone - VPS Deployment Control Panel

A self-hosted deployment control panel for your VPS. Deploy multiple GitHub repositories on a single server without port conflicts using Traefik for routing.

## Features

- **Simple 3-Step Workflow**: Import → Prepare → Deploy
- **Traefik Integration**: Automatic reverse proxy routing
- **No Port Conflicts**: Each app gets its own URL path
- **Django Backend**: Extensible API for future AI features
- **Modern React UI**: Professional interface with Tailwind CSS

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/yourusername/keystone.git
cd keystone
cp env.example .env
# Edit .env with your settings (especially DJANGO_SECRET_KEY for production)
```

### 2. Start Keystone

```bash
docker compose up -d --build
```

### 3. Access the Panel

- **Panel UI**: http://YOUR_VPS_IP
- **Traefik Dashboard**: http://YOUR_VPS_IP:8080
- **Login**: admin / admin (change in .env)

## How It Works

### Step 1: Import Repository
Add your GitHub repository URL (public repos work out of the box).

### Step 2: Prepare for Traefik
Keystone clones your repo, detects the app structure (Django, Node, etc.), and configures Traefik routing.

### Step 3: Deploy
Build the Docker image and run the container. Your app is now accessible at:

```
http://YOUR_VPS_IP/your-app-name
```

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │              Traefik                │
                    │         (Reverse Proxy)             │
                    │            Port 80                  │
                    └────────────────┬────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
           ▼                         ▼                         ▼
    ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
    │  Keystone   │          │   Your App  │          │   Your App  │
    │    Panel    │          │     #1      │          │     #2      │
    │   (React)   │          │  /app-one   │          │  /app-two   │
    └─────────────┘          └─────────────┘          └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  Keystone   │
    │    API      │
    │  (Django)   │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │ PostgreSQL  │
    └─────────────┘
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | keystone | Database name |
| `POSTGRES_USER` | keystone | Database user |
| `POSTGRES_PASSWORD` | keystone | Database password |
| `DJANGO_SECRET_KEY` | (random) | Django secret key |
| `DJANGO_DEBUG` | 1 | Debug mode (set to 0 for production) |
| `KEYSTONE_ADMIN_USERNAME` | admin | Admin username |
| `KEYSTONE_ADMIN_PASSWORD` | admin | Admin password |

## Deploying Your Apps

### Django Apps
Keystone auto-detects Django apps (by `manage.py`) and generates a Dockerfile using Gunicorn.

**Required files in your repo:**
- `requirements.txt`
- `manage.py`

**Default settings:**
- Container port: 8000
- WSGI: `config.wsgi:application` (customize via environment variables)

### Node Apps
Keystone auto-detects Node apps (by `package.json`).

**Required files in your repo:**
- `package.json`

### Custom Dockerfile
If your repo has a `Dockerfile`, Keystone uses it as-is.

## Security

- Change default admin password in production
- Set a strong `DJANGO_SECRET_KEY`
- Consider adding HTTPS (Traefik supports Let's Encrypt)

## Development

### Backend (Django)
```bash
cd platform/backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend (React)
```bash
cd platform/frontend
npm install
npm run dev
```

## Future Roadmap

- [ ] HTTPS with Let's Encrypt
- [ ] GitHub webhook integration
- [ ] AI-powered troubleshooting
- [ ] AI-powered debugging
- [ ] Multi-user support with roles

## License

MIT
