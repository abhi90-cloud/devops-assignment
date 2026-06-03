# Security Documentation — AI Sentiment Analysis Platform

> **Repository:** https://github.com/abhi90-cloud/devops-assignment
> **Production URL:** https://ai-backend.astrodirectory.in
> **Monitoring URL:** https://monitoring.astrodirectory.in

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Security Architecture Diagram](#security-architecture-diagram)
3. [Network Security](#network-security)
4. [Transport Security](#transport-security)
5. [Application Security](#application-security)
6. [Server Security](#server-security)
7. [Container Security](#container-security)
8. [Secrets Management](#secrets-management)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Security Incident Response](#security-incident-response)
11. [Security Checklist](#security-checklist)
12. [Compliance Considerations](#compliance-considerations)
13. [Future Security Improvements](#future-security-improvements)

---

## Security Overview

The AI Sentiment Analysis Platform is secured through a defense-in-depth strategy — multiple overlapping security layers ensure that no single point of failure can compromise the system. Security controls exist at the network edge (Cloudflare), transport layer (TLS/HTTPS), host level (UFW, Fail2ban), application layer (FastAPI validation, authentication), and container layer (non-root execution, network isolation).

This document serves as the authoritative reference for all security policies, procedures, and configurations applicable to this platform. It must be reviewed and updated quarterly, or after any security incident.

**Security Principles Applied:**

| Principle | Implementation |
|-----------|----------------|
| Least Privilege | Containers run as non-root; DB user has minimal permissions |
| Defense in Depth | Cloudflare → UFW → NGINX → App validation — multiple layers |
| Zero Trust | No inter-service trust assumed; all internal calls validated |
| Immutable Infrastructure | Containers rebuilt from source on every deploy, not patched in place |
| Secrets Separation | No secrets in source code; all via environment variables and GitHub Secrets |
| Fail Secure | Application returns generic errors; detailed errors never exposed to clients |

---

## Security Architecture Diagram

```
                    ┌──────────────────────────────────────────┐
                    │             THREAT LANDSCAPE              │
                    │  DDoS / Bots / Scrapers / Scanners / CVE │
                    └──────────────────┬───────────────────────┘
                                       │
                    ┌──────────────────▼───────────────────────┐
                    │              CLOUDFLARE EDGE              │
                    │  ┌─────────┐ ┌─────┐ ┌──────────────┐   │
                    │  │   WAF   │ │ DDoS│ │ Rate Limiter │   │
                    │  │  Rules  │ │Prot.│ │   (req/min)  │   │
                    │  └─────────┘ └─────┘ └──────────────┘   │
                    │         IP Masking / TLS Edge             │
                    └──────────────────┬───────────────────────┘
                                       │ HTTPS only
                    ┌──────────────────▼───────────────────────┐
                    │           AWS EC2 HOST BOUNDARY           │
                    │  ┌──────────────────────────────────┐    │
                    │  │         UFW FIREWALL              │    │
                    │  │  ALLOW: 22, 80, 443 only          │    │
                    │  │  DENY:  all other inbound          │    │
                    │  └──────────────┬───────────────────┘    │
                    │                 │                         │
                    │  ┌──────────────▼───────────────────┐    │
                    │  │     NGINX (SSL Termination)        │    │
                    │  │  TLS 1.2+, HSTS, Security Headers │    │
                    │  └──────────────┬───────────────────┘    │
                    │                 │ Internal Docker Bridge  │
                    │  ┌──────────────▼───────────────────┐    │
                    │  │     DOCKER NETWORK (app_network)  │    │
                    │  │  ┌─────────┐   ┌──────────────┐  │    │
                    │  │  │ FastAPI │   │   Postgres   │  │    │
                    │  │  │  Auth + │   │  SSL conn    │  │    │
                    │  │  │ Validate│   │  restricted  │  │    │
                    │  │  └────┬────┘   └──────────────┘  │    │
                    │  │       │        ┌──────────────┐   │    │
                    │  │       └───────►│    Redis     │   │    │
                    │  │                │  auth + ACL  │   │    │
                    │  │                └──────────────┘   │    │
                    │  └───────────────────────────────────┘    │
                    └──────────────────────────────────────────-┘
```

---

## Network Security

### Cloudflare — Edge Security Layer

Cloudflare acts as the first line of defense, absorbing and filtering threats before they reach the origin server.

#### DDoS Protection

Cloudflare provides automatic volumetric DDoS mitigation at layers 3, 4, and 7. No manual configuration is required for the free tier; enterprise-grade mitigation is applied automatically for attacks exceeding 1 Tbps.

```
Cloudflare DDoS Protection Tiers:
├── L3/L4: SYN floods, UDP amplification, ICMP floods — automatic
├── L7:    HTTP floods, slowloris, resource exhaustion — WAF + rate limit rules
└── Bot Management: automated crawlers, credential stuffing attempts
```

#### Web Application Firewall (WAF)

The Cloudflare WAF is configured with the OWASP Core Ruleset enabled to block:
- SQL Injection (SQLi) attempts
- Cross-Site Scripting (XSS) payloads
- Remote File Inclusion (RFI)
- Local File Inclusion (LFI)
- Command Injection

```
Cloudflare WAF Configuration:
  Security Level:     Medium
  Challenge Passage:  30 minutes
  Browser Integrity:  On
  OWASP Ruleset:      Managed Rules — All enabled
  Custom Rules:       Block requests without valid User-Agent header
```

#### Rate Limiting

Cloudflare rate limiting rules prevent API abuse and brute-force attacks:

| Rule Name | Match | Threshold | Action | Period |
|-----------|-------|-----------|--------|--------|
| API Rate Limit | `/api/*` | 100 req/min per IP | Challenge | 1 minute |
| Auth Brute Force | `/api/v1/auth/*` | 10 req/min per IP | Block | 10 minutes |
| Health Scrape | `/health` | 60 req/min per IP | Throttle | 1 minute |
| Global Limit | `/*` | 500 req/min per IP | Block | 1 minute |

#### IP Masking and Origin Protection

With Cloudflare proxy enabled (orange cloud in DNS settings), the EC2 instance's public IP is never exposed to end users or attackers. Direct-to-IP attacks are blocked at the Cloudflare edge. The origin server should be configured to only accept connections from Cloudflare IP ranges:

```bash
# /opt/scripts/cloudflare_ip_whitelist.sh
# Allows only Cloudflare IPs on port 80/443 — all other sources blocked

CLOUDFLARE_IPS=(
    "103.21.244.0/22"
    "103.22.200.0/22"
    "103.31.4.0/22"
    "104.16.0.0/13"
    "104.24.0.0/14"
    "108.162.192.0/18"
    "131.0.72.0/22"
    "141.101.64.0/18"
    "162.158.0.0/15"
    "172.64.0.0/13"
    "173.245.48.0/20"
    "188.114.96.0/20"
    "190.93.240.0/20"
    "197.234.240.0/22"
    "198.41.128.0/17"
)

# Reset HTTP/HTTPS rules
sudo ufw delete allow 80/tcp
sudo ufw delete allow 443/tcp

# Allow only Cloudflare IPs
for IP in "${CLOUDFLARE_IPS[@]}"; do
    sudo ufw allow from "$IP" to any port 80 proto tcp
    sudo ufw allow from "$IP" to any port 443 proto tcp
done

sudo ufw reload
```

### UFW Firewall Configuration

The host-level firewall provides the second layer of network security:

```bash
# Current UFW ruleset
sudo ufw status verbose
```

```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
80/tcp                     ALLOW IN    Cloudflare IPs only
443/tcp                    ALLOW IN    Cloudflare IPs only
All ports                  DENY IN     Anywhere (default)
```

**Ports NOT exposed to the internet:**

| Port | Service | Access |
|------|---------|--------|
| 5432 | PostgreSQL | Internal Docker network only |
| 6379 | Redis | Internal Docker network only |
| 9090 | Prometheus | Internal Docker network only |
| 9093 | AlertManager | Internal Docker network only |
| 8000 | FastAPI | Internal Docker network only |

---

## Transport Security

### HTTPS Enforcement

All traffic to the platform is served over HTTPS. HTTP requests are automatically redirected to HTTPS at the NGINX layer:

```nginx
# /etc/nginx/conf.d/redirect.conf
server {
    listen 80;
    server_name ai-backend.astrodirectory.in monitoring.astrodirectory.in;
    return 301 https://$host$request_uri;
}
```

### TLS Configuration

NGINX is configured to enforce modern TLS standards:

```nginx
# /etc/nginx/conf.d/ssl.conf
ssl_protocols              TLSv1.2 TLSv1.3;
ssl_ciphers                ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers  off;
ssl_session_cache          shared:SSL:10m;
ssl_session_timeout        1d;
ssl_session_tickets        off;
ssl_stapling               on;
ssl_stapling_verify        on;
resolver                   1.1.1.1 8.8.8.8 valid=300s;
resolver_timeout           5s;
```

**TLS version support:**

| Protocol | Status | Reason |
|----------|--------|--------|
| SSLv2 | Disabled | Obsolete, multiple critical vulnerabilities |
| SSLv3 | Disabled | POODLE vulnerability |
| TLS 1.0 | Disabled | BEAST, deprecated by RFC 8996 |
| TLS 1.1 | Disabled | Deprecated by RFC 8996 |
| TLS 1.2 | Enabled | Widely supported, secure |
| TLS 1.3 | Enabled | Most secure, preferred |

### HTTP Strict Transport Security (HSTS)

HSTS headers instruct browsers to only communicate with the domain over HTTPS, preventing SSL stripping attacks:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

This header is also configured via Cloudflare's HSTS settings with:
- max-age: 6 months (15768000 seconds)
- includeSubDomains: enabled
- Preload: enabled (submitted to browser HSTS preload list)

### Security Headers

All responses from NGINX include the following security headers:

```nginx
# /etc/nginx/conf.d/security_headers.conf

add_header X-Frame-Options              "SAMEORIGIN" always;
add_header X-Content-Type-Options       "nosniff" always;
add_header X-XSS-Protection             "1; mode=block" always;
add_header Referrer-Policy              "strict-origin-when-cross-origin" always;
add_header Permissions-Policy           "geolocation=(), microphone=(), camera=()" always;
add_header Content-Security-Policy      "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';" always;
add_header Strict-Transport-Security    "max-age=31536000; includeSubDomains; preload" always;

# Remove server version disclosure
server_tokens off;
```

### Secure Cookie Configuration

FastAPI session and authentication cookies are configured with security attributes:

```python
# app/core/security.py
response.set_cookie(
    key="session_token",
    value=token,
    httponly=True,      # Prevents JavaScript access (XSS mitigation)
    secure=True,        # Only sent over HTTPS
    samesite="strict",  # Prevents CSRF attacks
    max_age=3600,       # 1 hour TTL
    path="/"
)
```

---

## Application Security

### FastAPI Input Validation

All API request bodies are validated using Pydantic models before any processing occurs. Invalid requests are rejected at the schema validation layer before reaching business logic:

```python
# app/schemas/analysis.py
from pydantic import BaseModel, Field, validator
import re

class AnalysisRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text to analyze for sentiment"
    )

    @validator("text")
    def sanitize_text(cls, v):
        # Strip null bytes and control characters
        v = v.replace("\x00", "")
        v = re.sub(r"[\x01-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", v)
        return v.strip()
```

### Input Sanitization

Beyond Pydantic validation, the application applies additional sanitization:

```python
# app/core/sanitization.py
import html
import bleach

def sanitize_text_input(text: str) -> str:
    """
    Sanitize text input to prevent injection attacks.
    Applied before any database write or ML inference.
    """
    # HTML escape to neutralize any markup
    text = html.escape(text)

    # Strip any allowed HTML tags (bleach whitelist approach)
    text = bleach.clean(text, tags=[], attributes={}, strip=True)

    # Normalize whitespace
    text = " ".join(text.split())

    return text
```

### Authentication and Authorization

API endpoints requiring authentication use JWT (JSON Web Tokens) with short expiry:

```python
# app/core/auth.py
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("SECRET_KEY")  # From environment — never hardcoded
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
```

### Error Handling — No Information Leakage

The application returns generic error messages to clients, preventing stack trace or internal information disclosure:

```python
# app/core/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

async def generic_exception_handler(request: Request, exc: Exception):
    # Log full error internally
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # Return generic message to client — never expose internal details
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."}
    )

# 422 Validation errors — sanitize field names but do not leak schema internals
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed. Check your input and retry."}
    )
```

### SQL Injection Prevention

All database queries use parameterized statements via SQLAlchemy ORM. Raw SQL is never constructed from user input:

```python
# SECURE — parameterized query via ORM
result = await db.execute(
    select(SentimentAnalysis).where(SentimentAnalysis.id == analysis_id)
)

# NEVER do this — direct string interpolation
# result = await db.execute(f"SELECT * FROM sentiment_analysis WHERE id = '{analysis_id}'")
```

### CORS Configuration

Cross-Origin Resource Sharing is configured to only allow requests from trusted origins:

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## Server Security

### SSH Hardening

SSH is the only administrative access method. The SSH daemon is hardened to prevent unauthorized access:

```bash
# /etc/ssh/sshd_config (hardened configuration)

# Disable root login
PermitRootLogin no

# Disable password authentication — key-based auth only
PasswordAuthentication no
ChallengeResponseAuthentication no
UsePAM no

# Only allow specific users
AllowUsers ubuntu

# Restrict SSH protocol version
Protocol 2

# Change default port (security through obscurity — optional)
# Port 2222

# Limit authentication attempts
MaxAuthTries 3
MaxSessions 5

# Disconnect idle sessions after 15 minutes
ClientAliveInterval 300
ClientAliveCountMax 3

# Disable X11 forwarding
X11Forwarding no

# Disable TCP forwarding
AllowTcpForwarding no

# Log level
LogLevel VERBOSE
```

Apply the configuration:

```bash
sudo sshd -t  # Test configuration validity
sudo systemctl restart sshd
```

### Fail2ban Configuration

Fail2ban monitors authentication logs and automatically bans IPs with repeated failures:

```ini
# /etc/fail2ban/jail.local

[DEFAULT]
bantime  = 3600       # Ban for 1 hour
findtime = 600        # Within 10-minute window
maxretry = 5          # After 5 failures

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
maxretry = 3
bantime  = 86400     # 24-hour ban for SSH brute force

[nginx-http-auth]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/error.log

[nginx-noscript]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/access.log
maxretry = 6
```

```bash
# Verify Fail2ban is active
sudo fail2ban-client status

# Check SSH jail
sudo fail2ban-client status sshd

# Manually unban an IP
sudo fail2ban-client set sshd unbanip <IP_ADDRESS>
```

### Automatic Security Updates

Unattended upgrades ensure security patches are applied automatically:

```bash
# /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Mail "admin@astrodirectory.in";
```

```bash
# Enable automatic updates
sudo dpkg-reconfigure --priority=low unattended-upgrades

# Verify configuration
sudo unattended-upgrade --dry-run --debug
```

### Audit Logging

The `auditd` daemon records sensitive system calls for forensic purposes:

```bash
# Install auditd
sudo apt-get install -y auditd audispd-plugins

# /etc/audit/rules.d/security.rules

# Log all authentication events
-w /var/log/auth.log -p wa -k auth_events

# Log Docker daemon access
-w /usr/bin/docker -p x -k docker_exec
-w /var/lib/docker -p wa -k docker_files

# Log changes to sensitive files
-w /etc/passwd -p wa -k identity_changes
-w /etc/shadow -p wa -k identity_changes
-w /etc/sudoers -p wa -k privilege_escalation
-w /opt/ai-sentiment/.env -p r -k secrets_access

# Log privilege escalation
-a always,exit -F arch=b64 -S setuid -k privilege_escalation
-a always,exit -F arch=b64 -S setgid -k privilege_escalation

sudo systemctl enable auditd
sudo systemctl restart auditd
```

---

## Container Security

### Non-Root Container Execution

All application containers run as non-root users to limit blast radius if a container is compromised:

```dockerfile
# Dockerfile (FastAPI)
FROM python:3.12-slim

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1001 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup . .

# Switch to non-root user before starting the application
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Resource Limits

Container resource limits prevent a single container from exhausting host resources (denial-of-service mitigation):

```yaml
# docker-compose.yml — resource constraints
services:
  fastapi:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          cpus: "0.25"
          memory: 256M

  postgres:
    deploy:
      resources:
        limits:
          cpus: "0.75"
          memory: 768M

  redis:
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 256M
```

### Network Isolation

Containers only communicate via the dedicated `app_network` Docker bridge. No container has unnecessary access to other containers:

```yaml
# docker-compose.yml — network isolation
networks:
  app_network:
    driver: bridge
    internal: false    # NGINX needs external access for SSL
  db_network:
    driver: bridge
    internal: true     # Database network — no external access at all

services:
  fastapi:
    networks:
      - app_network
      - db_network   # FastAPI needs DB and cache access

  postgres:
    networks:
      - db_network   # PostgreSQL only on internal network

  redis:
    networks:
      - db_network   # Redis only on internal network

  nginx:
    networks:
      - app_network  # NGINX only needs app access
```

### Docker Image Security Scanning

Images are scanned for known CVEs before deployment using Trivy in the CI pipeline:

```yaml
# .github/workflows/ci.yml
- name: Scan Docker image for vulnerabilities
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.DOCKER_IMAGE }}:${{ github.sha }}
    format: table
    exit-code: 1              # Fail pipeline on CRITICAL CVEs
    severity: CRITICAL,HIGH
    ignore-unfixed: true
```

### Read-Only Filesystems

Containers use read-only root filesystems where possible, with explicit tmpfs mounts for writable areas:

```yaml
# docker-compose.yml
services:
  fastapi:
    read_only: true
    tmpfs:
      - /tmp
      - /var/tmp
    volumes:
      - ./logs:/app/logs  # Named mount for log output only
```

### Volume Permissions

Named volumes are initialized with correct ownership to prevent privilege escalation via mounted volumes:

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      device: /opt/data/postgres
      o: "bind,uid=999,gid=999"  # PostgreSQL container user
```

---

## Secrets Management

### GitHub Secrets

All sensitive credentials are stored as GitHub Encrypted Secrets, never in source code or committed files. The secrets are injected as environment variables during GitHub Actions workflow execution.

```
Repository Secrets:
├── EC2_SSH_KEY         → Private key for EC2 SSH access
├── EC2_HOST            → EC2 instance IP or hostname
├── EC2_USER            → SSH user (ubuntu)
├── DOCKER_USERNAME     → Docker Hub registry login
├── DOCKER_PASSWORD     → Docker Hub access token (not password)
├── DB_PASSWORD         → PostgreSQL production password
├── REDIS_PASSWORD      → Redis AUTH password
├── SECRET_KEY          → FastAPI JWT signing key
└── GRAFANA_PASSWORD    → Grafana admin password
```

### Environment Variable Strategy

The `.env` file is generated at deployment time by the GitHub Actions workflow and is never stored in the repository:

```yaml
# .github/workflows/deploy.yml
- name: Write environment file
  run: |
    cat > .env << EOF
    POSTGRES_PASSWORD=${{ secrets.DB_PASSWORD }}
    REDIS_PASSWORD=${{ secrets.REDIS_PASSWORD }}
    SECRET_KEY=${{ secrets.SECRET_KEY }}
    GF_SECURITY_ADMIN_PASSWORD=${{ secrets.GRAFANA_PASSWORD }}
    EOF
```

### `.gitignore` Strategy

The following files are explicitly excluded from version control:

```gitignore
# .gitignore

# Environment files — NEVER commit
.env
.env.*
!.env.example

# SSL certificates
*.pem
*.key
*.crt
*.p12

# Backup files
*.dump
*.sql.gz
*.rdb

# Local override files
docker-compose.override.yml

# Python cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Logs
*.log
logs/
```

### Credential Rotation Policy

| Credential | Rotation Frequency | Method |
|------------|--------------------|--------|
| SSH Key (EC2) | Every 90 days | Rotate in AWS console, update GitHub Secret |
| PostgreSQL password | Every 90 days | Update .env + DB user, restart containers |
| Redis password | Every 90 days | Update .env + Redis config, restart containers |
| JWT SECRET_KEY | Every 30 days | Update GitHub Secret, triggers re-auth for all sessions |
| Grafana admin password | Every 90 days | Update via Grafana UI + GitHub Secret |
| Docker Hub token | Every 180 days | Regenerate in Docker Hub, update GitHub Secret |

```bash
# Credential rotation script template
#!/bin/bash
# /opt/scripts/rotate_credentials.sh

# Generate new PostgreSQL password
NEW_PG_PASS=$(openssl rand -base64 32 | tr -d /=+)

# Update PostgreSQL user password
docker compose exec postgres psql -U postgres \
    -c "ALTER USER sentiment_user WITH PASSWORD '${NEW_PG_PASS}';"

# Update .env file
sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${NEW_PG_PASS}/" /opt/ai-sentiment/.env

# Restart FastAPI to pick up new credentials
docker compose restart fastapi

echo "Credentials rotated. Update GitHub Secret DB_PASSWORD manually."
```

---

## Monitoring and Alerting

### Prometheus Security Alert Rules

```yaml
# prometheus/alerts/security_alerts.yml
groups:
  - name: security_alerts
    rules:

      - alert: HighHTTPErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m]) /
          rate(http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High HTTP 5xx error rate: {{ $value | humanizePercentage }}"
          description: "More than 5% of requests are returning 5xx errors"

      - alert: SuspiciousLoginAttempts
        expr: increase(failed_login_attempts_total[5m]) > 20
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Possible brute-force attack detected"
          description: "{{ $value }} failed login attempts in the last 5 minutes"

      - alert: UnauthorizedAPIAccess
        expr: increase(http_requests_total{status="401"}[5m]) > 50
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High rate of unauthorized API requests"

      - alert: ContainerRunningAsRoot
        expr: container_processes_running{user="root"} > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.container }} has a root process running"

      - alert: AbnormalOutboundConnections
        expr: increase(node_network_transmit_bytes_total[5m]) > 1e9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Unusually high outbound traffic — possible data exfiltration"
```

### AlertManager Routing Rules

```yaml
# alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: "smtp.gmail.com:465"
  smtp_from: "alerts@astrodirectory.in"
  smtp_auth_username: "alerts@astrodirectory.in"
  smtp_auth_password: "${SMTP_PASSWORD}"

route:
  group_by: [alertname, severity]
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 3h
  receiver: email_alerts

  routes:
    - match:
        severity: critical
      receiver: pagerduty_critical
      repeat_interval: 30m

receivers:
  - name: email_alerts
    email_configs:
      - to: "admin@astrodirectory.in"
        send_resolved: true

  - name: pagerduty_critical
    pagerduty_configs:
      - routing_key: "${PAGERDUTY_ROUTING_KEY}"
        send_resolved: true
```

### Grafana Security Dashboard

A dedicated security dashboard monitors:
- HTTP 4xx/5xx error rates (spike detection)
- Authentication failure counts
- Failed login attempts per IP
- Container process count by user
- Outbound network traffic anomalies
- Disk write activity (ransomware indicator)

Access the dashboard at: https://monitoring.astrodirectory.in (admin/admin)

---

## Security Incident Response

The following procedure outlines the steps to take upon detecting or suspecting a security incident.

### Phase 1 — Detection

```
Indicators of Compromise (IoC) to watch for:
├── Unusual outbound connections to unknown IPs
├── Unexpected processes running inside containers
├── Database queries from unusual source IPs
├── Spike in 401/403 responses in NGINX logs
├── Fail2ban banning large numbers of IPs simultaneously
├── Container restarting unexpectedly (possible memory-based attack)
└── Unexpected files in container volumes
```

```bash
# Immediate detection commands
# Check active network connections
sudo ss -tlnp
sudo netstat -antp | grep ESTABLISHED

# Check for unexpected processes
docker compose exec fastapi ps aux
docker top $(docker compose ps -q fastapi)

# Check for unexpected outbound connections
sudo lsof -i -n | grep ESTABLISHED | grep -v "ssh\|https"

# Review recent authentication failures
sudo grep "Failed password\|Invalid user" /var/log/auth.log | tail -50

# Check Cloudflare Firewall Events for DDoS indicators
# (Review in Cloudflare dashboard: Security → Firewall Events)
```

### Phase 2 — Containment

```bash
# Option A: Block suspicious IP immediately
sudo ufw insert 1 deny from <SUSPICIOUS_IP>

# Option B: Isolate a compromised container
docker network disconnect app_network <container_name>

# Option C: Emergency full shutdown (extreme measure)
docker compose down

# Option D: Revoke compromised SSH key
# Remove the key from ~/.ssh/authorized_keys
sed -i '/COMPROMISED_KEY_FINGERPRINT/d' ~/.ssh/authorized_keys

# Enable Cloudflare Under Attack Mode (I'm Under Attack!)
# Cloudflare Dashboard → Security → Settings → Security Level → I'm Under Attack!
```

### Phase 3 — Eradication

```bash
# Rotate all credentials immediately
/opt/scripts/rotate_credentials.sh

# Rebuild containers from clean images (do not reuse potentially compromised images)
docker compose down
docker system prune -af
docker compose build --no-cache
docker compose up -d

# Verify no unauthorized processes remain
docker compose exec fastapi ps aux

# Audit all running container processes
for container in $(docker compose ps -q); do
    echo "=== Container: $container ==="
    docker top "$container"
done

# Check for backdoors in application code
git diff HEAD~10 -- "*.py" | grep -E "(subprocess|os.system|eval|exec)"
```

### Phase 4 — Recovery

```bash
# Restore from last known-clean backup if data integrity is in question
# Follow BACKUP_RESTORE.md restore procedures

# Re-enable services gradually
docker compose up -d postgres redis
sleep 30
docker compose up -d fastapi
sleep 10
docker compose up -d nginx

# Verify health
curl -s https://ai-backend.astrodirectory.in/health

# Re-enable Cloudflare normal security level
# Cloudflare Dashboard → Security → Settings → Security Level → Medium

# Monitor closely for 24 hours post-recovery
docker compose logs -f --tail=100
```

### Phase 5 — Postmortem

Within 72 hours of incident resolution, document:

```markdown
# Incident Postmortem — [DATE]

## Summary
Brief description of the incident, impact, and duration.

## Timeline
- HH:MM UTC — Alert triggered / Incident detected
- HH:MM UTC — Containment actions taken
- HH:MM UTC — Root cause identified
- HH:MM UTC — Eradication complete
- HH:MM UTC — Service fully restored

## Root Cause Analysis
What allowed this to happen? (Technical + process failures)

## Impact Assessment
- Services affected:
- Data at risk:
- User impact:
- Duration:

## Remediation Actions Taken
List of changes made during incident response.

## Preventive Measures
What will be done to prevent recurrence?

## Action Items
| Item | Owner | Due Date |
|------|-------|----------|
| ... | ... | ... |
```

---

## Security Checklist

### Daily

```bash
# Run this script daily (or review Grafana dashboards)
#!/bin/bash
echo "=== Daily Security Check $(date) ==="

# 1. All containers running as expected
echo "[1] Container status:"
docker compose ps

# 2. Check for failed SSH logins
echo "[2] SSH failures (last 24h):"
sudo grep "Failed password" /var/log/auth.log | grep "$(date +%b\ %d)" | wc -l

# 3. Check Fail2ban bans
echo "[3] Active Fail2ban bans:"
sudo fail2ban-client status sshd | grep "Currently banned"

# 4. Verify firewall is active
echo "[4] UFW status:"
sudo ufw status | head -5

# 5. Application health
echo "[5] API health:"
curl -s https://ai-backend.astrodirectory.in/health | python3 -m json.tool
```

### Weekly

- [ ] Review NGINX access logs for anomalous patterns (`/var/log/nginx/access.log`)
- [ ] Check Grafana security dashboard for unusual traffic patterns
- [ ] Verify Fail2ban jail statistics and review banned IPs
- [ ] Review Docker image vulnerability scan results from CI/CD
- [ ] Check disk usage — full disk can indicate log flooding attack
- [ ] Verify backup integrity checksums passed (review `/var/log/backup.log`)
- [ ] Review Cloudflare Firewall Events for WAF blocks

```bash
# Weekly NGINX log review
sudo grep -E "(401|403|404)" /var/log/nginx/access.log | \
    awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# Check for unusual user agents
sudo grep -E "(sqlmap|nikto|nmap|masscan|zgrab)" /var/log/nginx/access.log
```

### Monthly

- [ ] Rotate credentials per the credential rotation policy (see Secrets Management)
- [ ] Review and update UFW rules — remove stale allow rules
- [ ] Run full vulnerability scan: `trivy image <IMAGE_NAME>:latest`
- [ ] Test backup restore procedure (see BACKUP_RESTORE.md — Recovery Testing)
- [ ] Review GitHub repository access — remove stale collaborators
- [ ] Audit GitHub Actions secrets — remove unused secrets
- [ ] Check SSL certificate expiry dates
- [ ] Review Cloudflare WAF logs for emerging threat patterns

```bash
# Monthly SSL certificate expiry check
sudo certbot certificates
openssl x509 -in /etc/letsencrypt/live/ai-backend.astrodirectory.in/cert.pem \
    -noout -enddate

# Monthly Docker image age audit
docker images --format "{{.Repository}}:{{.Tag}} {{.CreatedSince}}"
```

### Quarterly

- [ ] Full penetration test or vulnerability assessment of the API
- [ ] Review and update this SECURITY.md document
- [ ] Conduct tabletop exercise for incident response scenarios
- [ ] Review IAM policies — AWS EC2 instance role, S3 bucket policies
- [ ] Renew or review Cloudflare WAF managed ruleset subscriptions
- [ ] Review audit log archives (`auditd`) for long-term anomaly patterns
- [ ] Validate disaster recovery procedure end-to-end (full DR drill)

---

## Compliance Considerations

While the platform does not currently operate in a regulated industry, the following compliance frameworks are relevant as the platform scales:

| Framework | Applicability | Current Status | Notes |
|-----------|--------------|----------------|-------|
| GDPR | If processing EU user text data | Partial | Data minimization applied; no PII stored in sentiment_analysis table |
| SOC 2 Type II | SaaS platform controls | Not certified | Controls largely aligned; formal audit not conducted |
| OWASP Top 10 | Application security | Addressed | Input validation, auth, error handling, injection prevention all implemented |
| CIS Benchmarks | Server hardening | Partial | SSH hardening, UFW, Fail2ban applied; full CIS Level 1 not audited |
| PCI DSS | Not applicable | N/A | No payment card data processed |

**Privacy Notes:**
- Text submitted for sentiment analysis may contain personally identifiable information (PII) from end users.
- If GDPR applies, implement a data retention policy with automatic deletion of analysis records after 90 days.
- Consider adding a data processing agreement (DPA) and privacy policy.

```sql
-- GDPR data retention enforcement (run monthly)
DELETE FROM sentiment_analysis
WHERE created_at < NOW() - INTERVAL '90 days';
```

---

## Future Security Improvements

| Priority | Improvement | Effort | Impact |
|----------|-------------|--------|--------|
| High | Migrate secrets to HashiCorp Vault or AWS Secrets Manager | Medium | High |
| High | Implement mTLS between containers (service mesh) | High | High |
| High | Add SIEM integration (e.g., Elastic Security or AWS Security Hub) | Medium | High |
| Medium | Enable AWS GuardDuty for EC2 threat detection | Low | Medium |
| Medium | Implement API key rotation mechanism for end-users | Medium | Medium |
| Medium | Add Content Security Policy reporting (`report-uri`) | Low | Medium |
| Medium | Integrate Dependabot for Python dependency CVE scanning | Low | Medium |
| Low | Add CrowdSec community IDS to augment Fail2ban | Low | Medium |
| Low | Conduct formal third-party penetration test | High | High |
| Low | Submit domain to HSTS preload list | Low | Low |

---

*DevOps Engineer Assignment — Deepak Sharma — June 2026*
