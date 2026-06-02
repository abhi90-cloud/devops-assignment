# 🚀 AI Sentiment Analysis Platform

![CI](https://img.shields.io/badge/CI-Passing-success?style=for-the-badge\&logo=githubactions)
![Docker](https://img.shields.io/badge/Docker-7_Containers-2496ED?style=for-the-badge\&logo=docker\&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Production](https://img.shields.io/badge/Production-Live-success?style=for-the-badge)

Production-grade AI Sentiment Analysis platform demonstrating modern DevOps practices, CI/CD automation, monitoring, security hardening, container orchestration, and operational excellence.

---

# 🌐 Live URLs

| Service              | URL                                               |
| -------------------- | ------------------------------------------------- |
| Production API       | https://ai-backend.astrodirectory.in              |
| Monitoring Dashboard | https://monitoring.astrodirectory.in              |
| API Documentation    | https://ai-backend.astrodirectory.in/docs         |
| ReDoc Documentation  | https://ai-backend.astrodirectory.in/redoc        |
| GitHub Repository    | https://github.com/abhi90-cloud/devops-assignment |

**Grafana Credentials**

```text
Username: admin
Password: admin
```

---

# ⚡ Quick Test

### Health Check

```bash
curl -s https://ai-backend.astrodirectory.in/health | jq
```

### Sentiment Prediction

```bash
curl -X POST \
"https://ai-backend.astrodirectory.in/predict?text=This%20platform%20is%20amazing" \
-H "accept: application/json"
```

### Analytics

```bash
curl -s https://ai-backend.astrodirectory.in/analytics | jq
```

---

# 📌 Overview

The AI Sentiment Analysis Platform is a production-ready FastAPI application deployed on AWS using Docker Compose. The platform performs sentiment analysis, stores prediction history in PostgreSQL, accelerates requests through Redis caching, and provides full observability through Prometheus, Grafana, and AlertManager. Automated CI/CD pipelines ensure safe, repeatable deployments with monitoring and rollback capabilities.

---

# 🏗️ Architecture

```text
┌──────────────────────────────┐
│          INTERNET            │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         CLOUDFLARE           │
│ Full SSL • CDN • WAF • DDoS  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      NGINX (80 / 443)        │
│ Reverse Proxy • Rate Limit   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐         ┌────────────────────────────┐
│     FASTAPI (8000)           │         │       CI/CD PIPELINE       │
│   Python 3.11 • 4 Workers    │◄────────┤ GitHub Actions            │
└───────┬─────────────┬─────────┘         │ ci → build → deploy       │
        │             │                   │ monitor → rollback        │
        ▼             ▼                   └────────────────────────────┘
┌──────────────┐ ┌──────────────┐
│POSTGRESQL    │ │ REDIS 7      │
│5432          │ │6379          │
│Indexed DB    │ │LRU + AOF     │
└──────┬───────┘ └──────┬───────┘
       │                │
       └───────┬────────┘
               │
               ▼

┌────────────────────────────────────────────────────────────┐
│                    MONITORING STACK                        │
├────────────────────────────────────────────────────────────┤
│ Prometheus (9090) → Grafana (3000) → AlertManager (9093) │
└────────────────────────────────────────────────────────────┘
```

---

# 🛠️ Tech Stack

| Category           | Technology           | Details                        |
| ------------------ | -------------------- | ------------------------------ |
| Backend            | FastAPI              | High-performance Python API    |
| Runtime            | Python 3.11          | Modern Python runtime          |
| Application Server | Uvicorn              | 4 worker processes             |
| Database           | PostgreSQL 16 Alpine | Indexed and optimized          |
| Cache              | Redis 7 Alpine       | LRU eviction, AOF persistence  |
| Reverse Proxy      | NGINX 1.25 Alpine    | SSL termination, rate limiting |
| CDN/WAF            | Cloudflare           | Full SSL, DDoS protection      |
| Containers         | Docker               | Containerized services         |
| Orchestration      | Docker Compose       | Multi-container deployment     |
| CI/CD              | GitHub Actions       | Automated pipelines            |
| Monitoring         | Prometheus           | Metrics collection             |
| Visualization      | Grafana              | Dashboards and reporting       |
| Alerting           | AlertManager         | Incident notifications         |
| Infrastructure     | AWS EC2 t2.medium    | Ubuntu 22.04                   |

---

# 📊 Services

| Service      | Port     | Status     | Description         |
| ------------ | -------- | ---------- | ------------------- |
| FastAPI      | 8000     | 🟢 Healthy | AI Sentiment Engine |
| PostgreSQL   | 5432     | 🟢 Healthy | Primary Data Store  |
| Redis        | 6379     | 🟢 Healthy | Cache Layer         |
| NGINX        | 80 / 443 | 🟢 Healthy | Reverse Proxy       |
| Prometheus   | 9090     | 🟢 Healthy | Metrics Collection  |
| Grafana      | 3000     | 🟢 Healthy | Dashboards          |
| AlertManager | 9093     | 🟢 Healthy | Alert Routing       |

---

# 📋 API Endpoints

| Method | Endpoint       | Description                |
| ------ | -------------- | -------------------------- |
| GET    | /health        | Health Check               |
| POST   | /predict       | Sentiment Prediction       |
| GET    | /predict?text= | Query Parameter Prediction |
| GET    | /predictions   | Prediction History         |
| GET    | /analytics     | Usage Analytics            |
| GET    | /metrics       | Prometheus Metrics         |
| GET    | /docs          | Swagger Documentation      |
| GET    | /redoc         | ReDoc Documentation        |

### Supported Sentiment Levels

```text
very_positive
positive
neutral
negative
very_negative
```

---

# 🔍 Example Prediction

### Request

```bash
curl -X POST \
"https://ai-backend.astrodirectory.in/predict?text=This%20application%20is%20excellent"
```

### Response

```json
{
  "text": "This application is excellent",
  "sentiment": "very_positive",
  "confidence": 0.98,
  "cached": false,
  "timestamp": "2026-06-01T12:00:00Z"
}
```

---

# 🔄 CI/CD Pipeline

### Deployment Flow

```text
Developer Push
      │
      ▼
   ci.yml
      │
      ▼
 build.yml
      │
      ▼
 deploy.yml
      │
      ▼
 Health Check
      │
      ├── Success → Production
      │
      └── Failure → rollback.yml
```

### Workflows

| File         | Trigger                 |
| ------------ | ----------------------- |
| ci.yml       | Push/PR to main/develop |
| build.yml    | Push to main            |
| deploy.yml   | After build success     |
| rollback.yml | Manual                  |
| monitor.yml  | Every 5 minutes         |
| pr-check.yml | Pull Requests           |

---

# 🚀 Quick Deploy

### Clone Repository

```bash
git clone https://github.com/abhi90-cloud/devops-assignment.git
cd devops-assignment
```

### Configure Environment

```bash
cp .env.example .env
```

### Start Platform

```bash
docker compose pull
docker compose up -d
```

### Verify Services

```bash
docker compose ps
```

---

# 📁 Project Structure

```text
devops-assignment/
│
├── app/
│   ├── main.py
│   ├── api/
│   ├── models/
│   ├── services/
│   └── database/
│
├── nginx/
│   ├── nginx.conf
│   └── conf.d/
│
├── monitoring/
│   ├── prometheus/
│   ├── grafana/
│   └── alertmanager/
│
├── backups/
│
├── scripts/
│   ├── deploy.sh
│   ├── rollback.sh
│   └── backup.sh
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── build.yml
│       ├── deploy.yml
│       ├── rollback.yml
│       ├── monitor.yml
│       └── pr-check.yml
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# 🔒 Security

## Infrastructure Security

* ✅ Cloudflare Full SSL
* ✅ Cloudflare DDoS Protection
* ✅ Cloudflare WAF
* ✅ UFW Firewall
* ✅ Fail2ban Protection
* ✅ Security Headers
* ✅ Reverse Proxy Isolation

## Application Security

* ✅ Rate Limiting (30 requests/sec)
* ✅ Non-root Containers
* ✅ Environment-based Secrets
* ✅ Input Validation
* ✅ Docker Network Isolation
* ✅ Private Container Registry

## Operational Security

* ✅ GitHub Secrets
* ✅ Automated Monitoring
* ✅ Health Checks
* ✅ Manual Rollback Capability

---

# 💾 Backup & Restore

### Backup Policy

| Component  | Method       | Schedule       | Retention |
| ---------- | ------------ | -------------- | --------- |
| PostgreSQL | pg_dump      | Daily 02:00 AM | 7 Days    |
| Redis      | RDB Snapshot | Daily 02:00 AM | 7 Days    |

### Restore Objectives

| Metric | Value        |
| ------ | ------------ |
| RPO    | < 24 Hours   |
| RTO    | < 15 Minutes |

---

# 📈 Monitoring

| Component    | Purpose                      |
| ------------ | ---------------------------- |
| Grafana      | Dashboards & Visualization   |
| Prometheus   | Metrics Collection           |
| AlertManager | Alert Routing                |
| /metrics     | Application Metrics Endpoint |

### Monitored Metrics

* API Response Times
* Request Volume
* Error Rates
* CPU Usage
* Memory Usage
* Container Health
* Database Availability
* Redis Availability

---

# 🔗 Links

| Resource          | URL                                               |
| ----------------- | ------------------------------------------------- |
| Production API    | https://ai-backend.astrodirectory.in              |
| API Docs          | https://ai-backend.astrodirectory.in/docs         |
| ReDoc             | https://ai-backend.astrodirectory.in/redoc        |
| Monitoring        | https://monitoring.astrodirectory.in              |
| GitHub Repository | https://github.com/abhi90-cloud/devops-assignment |
| DockerHub FastAPI | ab90909090hi/devops-fastapi                       |
| DockerHub NGINX   | ab90909090hi/devops-nginx                         |

---

# 📜 License

This project is licensed under the MIT License.

---

<div align="center">

**Built for the DevOps Engineer Assignment · June 2026**

</div>
