# Setup (Google Cloud VM, Ubuntu 24.04)

Open firewall ports:
- 22 (SSH)
- 8080 (Keystone Panel)
- 8000 (Keystone API)
- 9000–9999 (Deployed apps)

Run:
- cp .env.example .env
- docker compose up -d --build
