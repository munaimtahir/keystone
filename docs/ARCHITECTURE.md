# Architecture

## Core Components

1. Keystone UI
- Web-based control panel
- App management, deployment triggers, logs, and status

2. Keystone API
- Stores configuration
- Orchestrates deployments
- Communicates with Docker and Traefik

3. Deployment Engine
- Pulls repositories
- Builds images
- Runs docker-compose
- Applies routing rules

4. Traefik
- Central reverse proxy
- Single entrypoint for all HTTP traffic
- Routes requests to correct containers

5. Docker Runtime
- Runs all applications in isolated containers

## Traffic Flow

Client -> VPS IP -> Traefik -> Target App Container

## Control Flow

User -> Keystone UI -> Keystone API -> Deployment Engine -> Docker/Traefik
