# Deployment Guide — AI Sentiment Analysis Platform

> **Repository:** https://github.com/abhi90-cloud/devops-assignment
> **Production URL:** https://ai-backend.astrodirectory.in
> **Monitoring URL:** https://monitoring.astrodirectory.in

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Server Preparation](#server-preparation)
4. [Clone Repository](#clone-repository)
5. [Environment Configuration](#environment-configuration)
6. [DNS Configuration](#dns-configuration)
7. [SSL Setup](#ssl-setup)
8. [Docker Compose Deployment](#docker-compose-deployment)
9. [Deployment Verification](#deployment-verification)
10. [Updating the Application](#updating-the-application)
11. [Rollback Procedure](#rollback-procedure)
12. [Scaling Guide](#scaling-guide)
13. [Troubleshooting](#troubleshooting)
14. [Operational Runbook](#operational-runbook)

---

## Overview

This document describes the complete end-to-end deployment procedure for the AI Sentiment Analysis Platform on an AWS EC2 t2.medium instance running Ubuntu 22.04 LTS. Deployment is managed via Docker Compose with GitHub Actions driving automated CI/CD pipelines. All traffic is routed through Cloudflare before reaching the server.

---

## Prerequisites

Before beginning deployment, ensure the following are available and configured:

| Requirement | Version / Notes |
|-------------|----------------|
| AWS Account | EC2 t2.medium with Elastic IP assigned |
| Ubuntu | 22.04 LTS (Jammy) |
| Docker Engine | 24.x or later |
| Docker Compose | v2.x (plugin, not standalone) |
| Git | 2.x or later |
| Domain Name | Pointed to Cloudflare nameservers |
| Cloudflare Account | Free tier sufficient |
| GitHub Secrets | SSH key, Docker registry credentials |

### Required GitHub Secrets

Navigate to **Repository → Settings → Secrets and Variables → Actions** and configure:

| Secret Name | Value |
|-------------|-------|
| `EC2_SSH_KEY` | Private SSH key (PEM format) for EC2 access |
| `EC2_HOST` | Public IP or hostname of EC2 instance |
| `EC2_USER` | SSH username (typically `ubuntu`) |
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `DB_PASSWORD` | PostgreSQL production password |
| `SECRET_KEY` | FastAPI JWT secret key |

---

## Server Preparation

### 1. Connect to the EC2 Instance

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

### 2. Update System Packages

```bash
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get dist-upgrade -y
sudo reboot
```

### 3. Install Required Dependencies

```bash
# Install prerequisite packages
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban \
    unattended-upgrades
```

### 4. Install Docker Engine

```bash
# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add ubuntu user to docker group (avoid sudo for docker commands)
sudo usermod -aG docker ubuntu
newgrp docker

# Verify installation
docker --version
docker compose version
```

### 5. Configure UFW Firewall

```bash
# Reset to defaults
sudo ufw --force reset

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (critical — do this before enabling)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Verify
sudo ufw status verbose
```

### 6. Configure Fail2ban

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Verify SSH jail is active
sudo fail2ban-client status sshd
```

---

## Clone Repository

```bash
# Navigate to application directory
cd /opt
sudo mkdir -p ai-sentiment
sudo chown ubuntu:ubuntu ai-sentiment
cd ai-sentiment

# Clone repository
git clone https://github.com/abhi90-cloud/devops-assignment .

# Verify contents
ls -la
```

---

## Environment Configuration

Create the `.env` file in the repository root. **Never commit this file to Git.**

```bash
cp .env.example .env
nano .env
```

### Complete `.env` Reference

```bash
# ============================================================
# APPLICATION SETTINGS
# ============================================================

# FastAPI application environment
APP_ENV=production

# Application secret key — used for JWT token signing
# Generate with: openssl rand -hex 32
SECRET_KEY=your-super-secret-key-change-this-in-production

# Allowed CORS origins (comma-separated)
ALLOWED_ORIGINS=https://ai-backend.astrodirectory.in

# API version prefix
API_V1_PREFIX=/api/v1

# Number of Uvicorn worker processes
# Recommended: 2 * CPU cores + 1 = 5 for t2.medium
WORKERS=4

# ============================================================
# DATABASE SETTINGS
# ============================================================

# PostgreSQL connection details
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=sentiment_db
POSTGRES_USER=sentiment_user
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD_HERE

# Full DSN for SQLAlchemy
DATABASE_URL=postgresql+asyncpg://sentiment_user:CHANGE_THIS_STRONG_PASSWORD_HERE@postgres:5432/sentiment_db

# Connection pool settings
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# ============================================================
# REDIS SETTINGS
# ============================================================

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=CHANGE_THIS_REDIS_PASSWORD

# Cache TTL in seconds (3600 = 1 hour)
CACHE_TTL=3600

# Redis URL (used by some libraries)
REDIS_URL=redis://:CHANGE_THIS_REDIS_PASSWORD@redis:6379/0

# ============================================================
# MONITORING SETTINGS
# ============================================================

# Grafana admin credentials
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=CHANGE_THIS_GRAFANA_PASSWORD

# Prometheus retention period
PROMETHEUS_RETENTION=15d

# ============================================================
# DOCKER IMAGE SETTINGS
# ============================================================

# Docker Hub image tag for deployment
IMAGE_TAG=latest
DOCKER_IMAGE=your-dockerhub-username/ai-sentiment-api

# ============================================================
# DOMAIN SETTINGS
# ============================================================

DOMAIN=astrodirectory.in
API_SUBDOMAIN=ai-backend
MONITORING_SUBDOMAIN=monitoring
```

---

## DNS Configuration

### Cloudflare DNS Records

Log into Cloudflare dashboard → Select your domain → DNS → Records.

Add the following A records:

| Type | Name | Content | Proxy Status | TTL |
|------|------|---------|-------------|-----|
| A | `ai-backend` | `<EC2_ELASTIC_IP>` | Proxied (orange cloud) | Auto |
| A | `monitoring` | `<EC2_ELASTIC_IP>` | Proxied (orange cloud) | Auto |
| A | `www` | `<EC2_ELASTIC_IP>` | Proxied (orange cloud) | Auto |

### Cloudflare SSL/TLS Settings

Navigate to **SSL/TLS → Overview** and set encryption mode to **Full (Strict)**.

This ensures:
- Client ↔ Cloudflare: encrypted
- Cloudflare ↔ Origin: encrypted with valid certificate
- Prevents SSL stripping attacks

Also enable under **SSL/TLS → Edge Certificates**:
- Always Use HTTPS: **On**
- Minimum TLS Version: **TLS 1.2**
- Opportunistic Encryption: **On**
- TLS 1.3: **On**
- HSTS: **Enabled** (max-age: 6 months, includeSubDomains: yes)

---

## SSL Setup

### Install Certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain certificates for both subdomains
sudo certbot --nginx \
    -d ai-backend.astrodirectory.in \
    -d monitoring.astrodirectory.in \
    --non-interactive \
    --agree-tos \
    --email admin@astrodirectory.in

# Verify certificate
sudo certbot certificates
```

### Auto-Renewal

Certbot installs a systemd timer automatically. Verify:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

### Certificate Paths

```
/etc/letsencrypt/live/ai-backend.astrodirectory.in/
├── cert.pem        # Server certificate
├── chain.pem       # Intermediate chain
├── fullchain.pem   # cert.pem + chain.pem (use this in NGINX)
└── privkey.pem     # Private key
```

---

## Docker Compose Deployment

### First-Time Deployment

```bash
cd /opt/ai-sentiment

# Pull latest images
docker compose pull

# Build application image
docker compose build --no-cache

# Start all services in detached mode
docker compose up -d

# Verify all 7 containers are running
docker compose ps
```

### Expected Container Status

```
NAME           IMAGE                           STATUS          PORTS
nginx          nginx:latest                    Up 2 hours      0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
fastapi        ai-sentiment-api:latest         Up 2 hours
postgres       postgres:16                     Up 2 hours
redis          redis:7                         Up 2 hours
prometheus     prom/prometheus:latest          Up 2 hours
grafana        grafana/grafana:latest          Up 2 hours
alertmanager   prom/alertmanager:latest        Up 2 hours
```

### Common Docker Compose Commands

```bash
# View all container statuses
docker compose ps

# View logs for all services
docker compose logs -f

# View logs for specific service
docker compose logs -f fastapi

# Restart a specific service
docker compose restart fastapi

# Stop all services
docker compose down

# Stop and remove volumes (DESTRUCTIVE — deletes all data)
docker compose down -v

# Execute a command inside a container
docker compose exec fastapi bash

# View resource usage
docker stats
```

---

## Deployment Verification

Run these checks after every deployment to confirm the system is healthy.

### 1. Container Health Check

```bash
# All 7 containers must show "Up" status
docker compose ps

# Check for any restart loops
docker compose ps | grep "Restarting"
```

### 2. Application Health Check

```bash
# API health endpoint
curl -s https://ai-backend.astrodirectory.in/health | python3 -m json.tool

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "version": "1.0.0"
# }
```

### 3. API Functional Test

```bash
# Test sentiment analysis endpoint
curl -s -X POST https://ai-backend.astrodirectory.in/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "I absolutely love this product!"}' | python3 -m json.tool

# Expected response includes sentiment: "positive"
```

### 4. Monitoring Check

```bash
# Prometheus targets — all should be "UP"
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health"'

# Grafana login page accessible
curl -sI https://monitoring.astrodirectory.in | grep "HTTP/"
```

### 5. Database Connectivity

```bash
# Connect to PostgreSQL inside container
docker compose exec postgres psql -U sentiment_user -d sentiment_db -c "SELECT version();"

# Check table exists
docker compose exec postgres psql -U sentiment_user -d sentiment_db \
  -c "SELECT COUNT(*) FROM sentiment_analysis;"
```

### 6. Redis Connectivity

```bash
# Ping Redis
docker compose exec redis redis-cli ping
# Expected: PONG

# Check Redis info
docker compose exec redis redis-cli info server | head -20
```

---

## Updating the Application

### Automated Update (via GitHub Actions)

Push to `main` branch triggers the full CI/CD pipeline automatically:

```
git add .
git commit -m "feat: improve sentiment model accuracy"
git push origin main
# GitHub Actions deploys automatically
```

### Manual Update Procedure

```bash
cd /opt/ai-sentiment

# Pull latest code
git pull origin main

# Pull latest Docker images
docker compose pull

# Rebuild application image
docker compose build --no-cache fastapi

# Rolling restart — minimal downtime
docker compose up -d --no-deps fastapi

# Verify new version is running
docker compose logs -f fastapi --tail=50
```

---

## Rollback Procedure

### Automated Rollback (via GitHub Actions)

The `rollback.yml` workflow can be manually triggered from GitHub:

1. Navigate to **Actions → Rollback Deployment**
2. Click **Run workflow**
3. Enter the target image tag (e.g., `v1.2.3` or commit SHA)
4. Click **Run workflow**

### Manual Rollback

```bash
cd /opt/ai-sentiment

# List available image tags
docker images | grep ai-sentiment-api

# Roll back to specific tag
IMAGE_TAG=v1.2.3 docker compose up -d --no-deps fastapi

# Alternatively, use git to revert
git log --oneline -10
git checkout <previous-commit-sha>
docker compose build fastapi
docker compose up -d --no-deps fastapi

# Verify rollback
curl -s https://ai-backend.astrodirectory.in/health
```

---

## Scaling Guide

### Vertical Scaling (Resize EC2 Instance)

```bash
# 1. Stop the application gracefully
docker compose down

# 2. Stop the EC2 instance via AWS Console
# 3. Change instance type (e.g., t2.medium → t2.large)
# 4. Start instance and reconnect

# 5. Restart application
cd /opt/ai-sentiment
docker compose up -d
```

### Horizontal Scaling (Multiple FastAPI Workers)

Increase Uvicorn workers inside the container (CPU-bound scaling):

```bash
# In .env file
WORKERS=8   # 2 * vCPUs + 1

# Restart FastAPI
docker compose up -d --no-deps fastapi
```

### Container Scaling (Multiple FastAPI Replicas)

For multi-node Docker Swarm or Kubernetes migration:

```bash
# With Docker Compose (single-node, load balanced by NGINX)
docker compose up -d --scale fastapi=3

# Requires NGINX upstream configuration with multiple backends
```

---

## Troubleshooting

### Container Crash / Restart Loop

```bash
# Identify the failing container
docker compose ps

# Get recent logs
docker compose logs --tail=100 <service_name>

# Inspect container exit code
docker inspect <container_id> | grep -A5 '"State"'

# Common fixes:
# - Environment variable misconfiguration → check .env
# - Port conflict → sudo ss -tlnp | grep <port>
# - Insufficient memory → docker stats
```

### Database Connection Refused

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres --tail=50

# Verify credentials match .env
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;"

# Check pg_hba.conf for connection restrictions
docker compose exec postgres cat /var/lib/postgresql/data/pg_hba.conf
```

### Redis Connection Failed

```bash
# Verify Redis container is running
docker compose exec redis redis-cli ping

# Check if password is configured
docker compose exec redis redis-cli -a $REDIS_PASSWORD ping

# Monitor Redis logs
docker compose logs redis --tail=50
```

### SSL Certificate Errors

```bash
# Check certificate validity
sudo certbot certificates

# Test SSL handshake
openssl s_client -connect ai-backend.astrodirectory.in:443 -servername ai-backend.astrodirectory.in

# Force certificate renewal
sudo certbot renew --force-renewal

# Reload NGINX after renewal
docker compose exec nginx nginx -s reload
```

### DNS Not Resolving

```bash
# Check DNS propagation
dig ai-backend.astrodirectory.in
nslookup ai-backend.astrodirectory.in

# Verify Cloudflare DNS record exists
# Flush local DNS cache (macOS)
sudo dscacheutil -flushcache

# Test direct EC2 IP access (bypasses Cloudflare)
curl -H "Host: ai-backend.astrodirectory.in" http://<EC2_IP>/health
```

### GitHub Actions Deployment Failure

```bash
# Check Actions logs in GitHub UI under Actions tab
# Common issues:

# SSH key issue — test manually
ssh -i ~/.ssh/deploy_key ubuntu@$EC2_HOST "echo connected"

# Docker registry auth failure
docker login -u $DOCKER_USERNAME -p $DOCKER_PASSWORD

# Disk space on EC2
df -h
docker system prune -af --volumes  # WARNING: removes unused images/volumes
```

---

## Operational Runbook

### Daily Operations Checklist

```bash
# 1. Verify all containers are running
docker compose ps

# 2. Check application health
curl -s https://ai-backend.astrodirectory.in/health

# 3. Review error logs from last 24 hours
docker compose logs --since=24h fastapi | grep -i error

# 4. Check disk usage
df -h && du -sh /var/lib/docker

# 5. Review Grafana dashboards
# https://monitoring.astrodirectory.in
```

### Restart All Services

```bash
cd /opt/ai-sentiment
docker compose restart
docker compose ps
```

### Emergency Stop

```bash
cd /opt/ai-sentiment
docker compose down

# To completely wipe and restart fresh (data will be preserved in volumes)
docker compose down
docker compose up -d
```

### Log Rotation

Docker handles log rotation via the daemon configuration:

```bash
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}

sudo systemctl restart docker
```

---

*DevOps Engineer Assignment — Deepak Sharma — June 2026*
